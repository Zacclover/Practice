// ============================================================
// 公开来源抓取 Worker：手动抓取只保存待总结原始快照，永不调用模型。
// 通过 Cloudflare Cron 定时运行；服务端密钥仅存在于 Worker 环境变量。
// ============================================================
const SUPABASE_HEADERS = (serviceRoleKey) => ({
  apikey: serviceRoleKey,
  Authorization: `Bearer ${serviceRoleKey}`,
  "Content-Type": "application/json",
});
const MAX_RESPONSE_BYTES = 1_500_000;
const MAX_EXTRACTED_TEXT_LENGTH = 12_000;
const REQUEST_TIMEOUT_MS = 20_000;

export default {
  async scheduled(_event, env, ctx) {
    ctx.waitUntil(runScheduledCapture(env));
  },
  async fetch(request, env) {
    const url = new URL(request.url);
    try {
      validateEnvironment(env);
      const token = readBearerToken(request);
      const user = await authenticateUser(env, token);
      if (url.pathname === "/manual-capture" && request.method === "POST") {
        const body = await request.json();
        const source = await getAuthorizedSource(env, body?.sourceId, user.id);
        const result = await captureSource(source, env, "manual");
        return Response.json({ ok: true, result });
      }
      const attachmentRoute = url.pathname.match(new RegExp(`^/candidate-attachments/(${UUID_PATTERN})(?:/(${UUID_PATTERN}))?$`, "i"));
      if (attachmentRoute && request.method === "GET" && attachmentRoute[2]) {
        return fetchAuthorizedCandidateImage(env, user.id, attachmentRoute[1], attachmentRoute[2]);
      }
      if (attachmentRoute && request.method === "DELETE" && !attachmentRoute[2]) {
        await deleteAuthorizedCandidate(env, user.id, attachmentRoute[1]);
        return new Response(null, { status: 204 });
      }
      return Response.json({ error: { message: "未找到接口。" } }, { status: 404 });
    } catch (error) {
      return Response.json({ error: { message: safeErrorMessage(error) } }, { status: 400 });
    }
  },
};

const UUID_PATTERN = "[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}";

// 允许单元测试与未来受认证的手动触发入口复用核心调度。
export async function runScheduledCapture(env) {
  validateEnvironment(env);
  const sources = await queryDueSources(env);
  const results = await Promise.allSettled(sources.map((source) => captureSource(source, env, "scheduled")));
  return {
    inspected: sources.length,
    succeeded: results.filter((result) => result.status === "fulfilled").length,
    failed: results.filter((result) => result.status === "rejected").length,
  };
}

async function queryDueSources(env) {
  const records = await supabaseRequest(
    env,
    "/rest/v1/competitor_sources?is_enabled=eq.true&select=id,workspace_id,tab_id,competitor_id,url,fetch_interval_hours,last_fetched_at",
  );
  return records.filter(isDueForCapture);
}

function isDueForCapture(source, now = Date.now()) {
  if (!source.last_fetched_at) return true;
  const lastFetchedAt = Date.parse(source.last_fetched_at);
  if (Number.isNaN(lastFetchedAt)) return true;
  const intervalHours = Number(source.fetch_interval_hours) || 24;
  return now - lastFetchedAt >= intervalHours * 60 * 60 * 1000;
}

async function captureSource(source, env, triggerType = "scheduled") {
  const run = await insertRecord(env, "source_capture_runs", {
    id: crypto.randomUUID(),
    workspace_id: source.workspace_id,
    tab_id: source.tab_id,
    source_id: source.id,
    trigger_type: triggerType,
    status: "running",
  });

  try {
    const previousSnapshot = await getLatestSnapshot(env, source.id);
    const page = await fetchPublicSource(source.url);
    const snapshot = await createSnapshot(page.extractedText);

    const savedSnapshot = await insertRecord(env, "source_capture_snapshots", {
      id: crypto.randomUUID(),
      workspace_id: source.workspace_id,
      tab_id: source.tab_id,
      source_id: source.id,
      run_id: run.id,
      canonical_url: page.canonicalUrl,
      extracted_text: snapshot.extractedText,
      content_hash: snapshot.contentHash,
      http_status: page.httpStatus,
      page_title: page.title,
      capture_mode: triggerType,
      summary_status: "pending",
    }, "resolution=ignore-duplicates,return=representation");

    const targetSnapshot = savedSnapshot || previousSnapshot;
    if (savedSnapshot?.id) {
      await Promise.all(page.imageUrls.map((image, sortOrder) => insertRecord(env, "source_capture_snapshot_images", {
        id: crypto.randomUUID(), workspace_id: source.workspace_id, tab_id: source.tab_id,
        snapshot_id: savedSnapshot.id, source_id: source.id, image_url: image.url,
        alt_text: image.alt, sort_order: sortOrder,
      }, "resolution=ignore-duplicates,return=minimal")));
    }

    // 抓取器只保存原始快照和公开图片；Candidate 必须由浏览器本地 AI 总结成功后创建。

    await updateRecord(env, "competitor_sources", source.id, {
      last_fetched_at: new Date().toISOString(),
    });
    await updateRecord(env, "source_capture_runs", run.id, {
      status: "succeeded",
      http_status: page.httpStatus,
      finished_at: new Date().toISOString(),
    });
    return { snapshotId: targetSnapshot?.id || null, pendingSummary: Boolean(savedSnapshot?.id), candidateQueued: false };
  } catch (error) {
    await updateRecord(env, "source_capture_runs", run.id, {
      status: "failed",
      error_message: safeErrorMessage(error),
      finished_at: new Date().toISOString(),
    });
    throw error;
  }
}

export async function fetchPublicSource(sourceUrl, fetchImpl = fetch) {
  if (!isSafePublicSourceUrl(sourceUrl)) {
    throw new Error("只允许抓取安全的公开 HTTPS 来源。");
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetchImpl(sourceUrl, {
      headers: {
        Accept: "text/html,application/xhtml+xml",
        "User-Agent": "CompetitorInsightsBot/0.1 (+https://zacclover-competitor.pages.dev)",
      },
      redirect: "manual",
      signal: controller.signal,
    });
    if (response.status >= 300 && response.status < 400) {
      throw new Error("来源发生重定向，等待人工确认目标地址后再抓取。");
    }
    if (!response.ok) throw new Error(`来源返回 HTTP ${response.status}。`);
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.toLowerCase().includes("text/html")) {
      throw new Error("来源不是可抓取的 HTML 页面。");
    }
    const contentLength = Number(response.headers.get("content-length"));
    if (Number.isFinite(contentLength) && contentLength > MAX_RESPONSE_BYTES) {
      throw new Error("来源页面超过抓取大小限制。");
    }
    const html = await response.text();
    if (new TextEncoder().encode(html).byteLength > MAX_RESPONSE_BYTES) {
      throw new Error("来源页面超过抓取大小限制。");
    }
    return {
      canonicalUrl: canonicalizeSourceUrl(sourceUrl),
      extractedText: extractReadableText(html),
      httpStatus: response.status,
      title: extractTitle(html),
      imageUrls: extractPublicImageUrls(html, sourceUrl),
    };
  } finally {
    clearTimeout(timeout);
  }
}

// HTML 图片仅解析 src；相对地址按公开页面解析，拒绝凭据、私网和非 HTTPS URL。
export function extractPublicImageUrls(html, sourceUrl) {
  const results = [];
  const seen = new Set();
  const pattern = /<img\b[^>]*?\bsrc\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))[^>]*>/gi;
  let match;
  while ((match = pattern.exec(html)) && results.length < 12) {
    try {
      const url = new URL(decodeHtmlEntities(match[1] || match[2] || match[3] || ""), sourceUrl).toString();
      if (!isSafePublicSourceUrl(url) || seen.has(url)) continue;
      seen.add(url);
      const altMatch = match[0].match(/\balt\s*=\s*(?:"([^"]*)"|'([^']*)')/i);
      results.push({ url: canonicalizeSourceUrl(url), alt: decodeHtmlEntities(altMatch?.[1] || altMatch?.[2] || "").slice(0, 240) });
    } catch { /* 忽略无法安全解析的图片地址。 */ }
  }
  return results;
}

export function isSafePublicSourceUrl(value) {
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" || url.username || url.password) return false;
    const hostname = url.hostname.toLowerCase();
    if (hostname === "localhost" || hostname.endsWith(".localhost") || isPrivateIpv4(hostname)) {
      return false;
    }
    return hostname.length > 0;
  } catch {
    return false;
  }
}

function isPrivateIpv4(hostname) {
  const octets = hostname.split(".").map(Number);
  if (octets.length !== 4 || octets.some((value) => !Number.isInteger(value) || value < 0 || value > 255)) {
    return false;
  }
  const [first, second] = octets;
  return first === 0 || first === 10 || first === 127 || first === 169 && second === 254 ||
    first === 172 && second >= 16 && second <= 31 || first === 192 && second === 168;
}

function canonicalizeSourceUrl(value) {
  const url = new URL(value);
  url.hash = "";
  return url.toString();
}

export function extractReadableText(html) {
  return decodeHtmlEntities(
    html
      .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, " ")
      .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, " ")
      .replace(/<noscript\b[^>]*>[\s\S]*?<\/noscript>/gi, " ")
      .replace(/<[^>]+>/g, " ")
      .replace(/\s+/g, " ")
      .trim(),
  ).slice(0, MAX_EXTRACTED_TEXT_LENGTH);
}

function extractTitle(html) {
  const match = html.match(/<title\b[^>]*>([\s\S]*?)<\/title>/i);
  return match ? decodeHtmlEntities(match[1].replace(/\s+/g, " ").trim()).slice(0, 180) : "";
}

function decodeHtmlEntities(value) {
  return value
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'");
}

export async function createSnapshot(text) {
  const extractedText = String(text).replace(/\s+/g, " ").trim();
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(extractedText));
  const contentHash = [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
  return { extractedText, contentHash };
}

export function shouldQueueCandidate(previousHash, currentHash) {
  return !previousHash || previousHash !== currentHash;
}

function buildSummary(text) {
  return text.slice(0, 500).trim();
}

async function getLatestSnapshot(env, sourceId) {
  const records = await supabaseRequest(
    env,
    `/rest/v1/source_capture_snapshots?source_id=eq.${encodeURIComponent(sourceId)}&select=id,content_hash&order=fetched_at.desc&limit=1`,
  );
  return records[0] || null;
}

// 手动入口用用户 JWT 确认身份，再以成员表验证来源归属；密钥从不返回浏览器。
function readBearerToken(request) {
  const match = (request.headers.get("Authorization") || "").match(/^Bearer\s+(.+)$/i);
  if (!match) throw new Error("请先登录后再抓取。");
  return match[1];
}

async function authenticateUser(env, token) {
  const response = await fetch(`${env.SUPABASE_URL}/auth/v1/user`, {
    headers: { apikey: env.SUPABASE_SERVICE_ROLE_KEY, Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error("登录已失效，请重新登录。");
  return response.json();
}

async function getAuthorizedSource(env, sourceId, userId) {
  if (!/^[0-9a-f-]{36}$/i.test(String(sourceId || ""))) throw new Error("来源无效。");
  const sources = await supabaseRequest(env, `/rest/v1/competitor_sources?id=eq.${encodeURIComponent(sourceId)}&select=id,workspace_id,tab_id,competitor_id,url,last_fetched_at`);
  const source = sources[0];
  if (!source) throw new Error("来源不存在。");
  const memberships = await supabaseRequest(env, `/rest/v1/workspace_members?workspace_id=eq.${source.workspace_id}&user_id=eq.${encodeURIComponent(userId)}&select=workspace_id&limit=1`);
  if (!memberships.length) throw new Error("无权访问此来源。");
  return source;
}

async function assertWorkspaceMember(env, workspaceId, userId) {
  const memberships = await supabaseRequest(env, `/rest/v1/workspace_members?workspace_id=eq.${workspaceId}&user_id=eq.${encodeURIComponent(userId)}&select=workspace_id&limit=1`);
  if (!memberships.length) throw new Error("无权访问此内容。");
}

// 附件读取由 Worker 重新校验候选归属和图片 URL，浏览器只接收无凭据的图片字节。
async function fetchAuthorizedCandidateImage(env, userId, candidateId, attachmentId) {
  const rows = await supabaseRequest(env, `/rest/v1/candidate_attachments?id=eq.${attachmentId}&candidate_id=eq.${candidateId}&select=image_url,workspace_id&limit=1`);
  const attachment = rows[0];
  if (!attachment) throw new Error("附件不存在。");
  await assertWorkspaceMember(env, attachment.workspace_id, userId);
  if (!isSafePublicSourceUrl(attachment.image_url)) throw new Error("附件地址不安全。");
  const response = await fetch(attachment.image_url, { redirect: "manual", headers: { Accept: "image/*" } });
  const type = response.headers.get("content-type") || "";
  if (!response.ok || !type.toLowerCase().startsWith("image/")) throw new Error("附件暂不可用。");
  const bytes = await response.arrayBuffer();
  if (bytes.byteLength > 5_000_000) throw new Error("附件超过大小限制。");
  return new Response(bytes, { headers: { "Content-Type": type, "Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff" } });
}

async function deleteAuthorizedCandidate(env, userId, candidateId) {
  const rows = await supabaseRequest(env, `/rest/v1/source_capture_candidates?id=eq.${candidateId}&select=workspace_id&limit=1`);
  if (!rows[0]) throw new Error("候选不存在。");
  await assertWorkspaceMember(env, rows[0].workspace_id, userId);
  await supabaseRequest(env, `/rest/v1/source_capture_candidates?id=eq.${candidateId}`, { method: "DELETE", headers: { Prefer: "return=minimal" } });
}

async function insertRecord(env, table, payload, prefer = "return=representation") {
  const records = await supabaseRequest(env, `/rest/v1/${table}`, {
    method: "POST",
    headers: { Prefer: prefer },
    body: JSON.stringify(payload),
  });
  return Array.isArray(records) ? records[0] : records;
}

async function updateRecord(env, table, id, payload) {
  return supabaseRequest(env, `/rest/v1/${table}?id=eq.${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { Prefer: "return=minimal" },
    body: JSON.stringify(payload),
  });
}

async function supabaseRequest(env, path, init = {}) {
  const response = await fetch(`${env.SUPABASE_URL}${path}`, {
    ...init,
    headers: { ...SUPABASE_HEADERS(env.SUPABASE_SERVICE_ROLE_KEY), ...(init.headers || {}) },
  });
  if (!response.ok) throw new Error(`数据服务返回 HTTP ${response.status}。`);
  if (response.status === 204) return null;
  return response.json();
}

function validateEnvironment(env) {
  if (!/^https:\/\//.test(env?.SUPABASE_URL || "") || !env?.SUPABASE_SERVICE_ROLE_KEY) {
    throw new Error("抓取 Worker 缺少受保护的 Supabase 服务端配置。");
  }
}

function safeErrorMessage(error) {
  return String(error?.message || "未知抓取错误").slice(0, 500);
}
