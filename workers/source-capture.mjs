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
const MAX_SUBPAGES_PER_CAPTURE = 30;

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
      const batchRoute = url.pathname.match(new RegExp(`^/capture-runs/(${UUID_PATTERN})$`, "i"));
      if (batchRoute && request.method === "DELETE") {
        await deleteAuthorizedCaptureRun(env, user.id, batchRoute[1]);
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
    const entryPage = await fetchPublicSource(source.url);
    const childResults = await Promise.allSettled(
      entryPage.subpageUrls.map((url) => fetchPublicSource(url)),
    );
    // Candidate 必须由浏览器本地 AI 总结成功后创建；入口页仅用于发现一层子页面，只保存正文明确描述功能更新的子页面，避免帮助/导航页进入审核队列。
    const successfulPages = childResults
      .filter((result) => result.status === "fulfilled")
      .map((result) => result.value)
      .filter(isExplicitFeatureUpdatePage);
    // 快照与图片元数据均按本批次写入，避免每页/每张图片各占一个 Worker 子请求。
    const savedSnapshots = successfulPages.length
      ? await saveRawSnapshots(env, source, run, successfulPages, triggerType)
      : [];

    await updateRecord(env, "competitor_sources", source.id, {
      last_fetched_at: new Date().toISOString(),
    });
    await updateRecord(env, "source_capture_runs", run.id, {
      status: "succeeded",
      http_status: entryPage.httpStatus,
      finished_at: new Date().toISOString(),
    });
    return {
      snapshotId: savedSnapshots[0]?.id || null,
      pendingSummary: savedSnapshots.length > 0,
      capturedPages: savedSnapshots.length,
      subpageFailures: childResults.filter((result) => result.status === "rejected").length,
      candidateQueued: false,
    };
  } catch (error) {
    await updateRecord(env, "source_capture_runs", run.id, {
      status: "failed",
      error_message: safeErrorMessage(error),
      finished_at: new Date().toISOString(),
    });
    throw error;
  }
}

// 同一 run 的页面快照先批量 upsert，再读取本批次 ID 后一次性写入图片元数据，控制 Worker 子请求预算。
async function saveRawSnapshots(env, source, run, pages, triggerType) {
  const prepared = await Promise.all(pages.map(async (page) => ({ page, snapshot: await createSnapshot(page.extractedText) })));
  const snapshotRows = prepared.map(({ page, snapshot }) => ({
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
  }));
  await supabaseRequest(env, "/rest/v1/source_capture_snapshots?on_conflict=run_id%2Ccanonical_url%2Ccontent_hash", {
    method: "POST",
    headers: { Prefer: "resolution=ignore-duplicates,return=minimal" },
    body: JSON.stringify(snapshotRows),
  });
  const savedSnapshots = await supabaseRequest(env,
    `/rest/v1/source_capture_snapshots?run_id=eq.${encodeURIComponent(run.id)}&select=id,canonical_url`,
  );
  const snapshotIdByUrl = new Map(savedSnapshots.map((item) => [item.canonical_url, item.id]));
  const imageRows = prepared.flatMap(({ page }) => page.imageUrls.map((image, sortOrder) => ({
    id: crypto.randomUUID(), workspace_id: source.workspace_id, tab_id: source.tab_id,
    snapshot_id: snapshotIdByUrl.get(page.canonicalUrl), source_id: source.id,
    image_url: image.url, alt_text: image.alt, sort_order: sortOrder,
  })).filter((item) => item.snapshot_id));
  if (imageRows.length) {
    await supabaseRequest(env, "/rest/v1/source_capture_snapshot_images", {
      method: "POST",
      headers: { Prefer: "resolution=ignore-duplicates,return=minimal" },
      body: JSON.stringify(imageRows),
    });
  }
  return savedSnapshots;
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
      subpageUrls: discoverFirstLevelSameOriginHtmlLinks(html, sourceUrl),
    };
  } finally {
    clearTimeout(timeout);
  }
}

// 子页面只有标题或正文明确表达产品发布、功能新增、改进或修复时才进入本地 AI 审核队列。
export function isExplicitFeatureUpdatePage(page) {
  const haystack = `${page?.title || ""} ${page?.extractedText || ""}`.toLowerCase();
  return /(release\s*notes?|changelog|what'?s\s*new|new\s+(feature|capabilit|integration|update)|feature\s*(release|update)|improvements?|bug\s*fix(?:es)?|功能更新|新功能|新增(功能|能力|支持|集成)|版本更新|发布说明|更新日志|功能改进|问题修复|修复[了]?)/i.test(haystack);
}

// 入口页仅发现一层同源公开 HTML 链接：不递归、不跨域、按文档顺序最多 30 条。
export function discoverFirstLevelSameOriginHtmlLinks(html, entryUrl) {
  const links = [];
  const seen = new Set();
  let entry;
  try { entry = new URL(entryUrl); } catch { return links; }
  const entryCanonical = canonicalizeSourceUrl(entry.href);
  const pattern = /<a\b[^>]*?\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))[^>]*>/gi;
  let match;
  while ((match = pattern.exec(html)) && links.length < MAX_SUBPAGES_PER_CAPTURE) {
    try {
      const rawHref = decodeHtmlEntities(match[1] || match[2] || match[3] || '').trim();
      if (!rawHref || rawHref.startsWith('#')) continue;
      const target = new URL(rawHref, entry);
      const canonical = canonicalizeSourceUrl(target.href);
      if (target.origin !== entry.origin || canonical === entryCanonical || !isSafePublicSourceUrl(canonical) || seen.has(canonical)) continue;
      seen.add(canonical);
      links.push(canonical);
    } catch { /* 忽略不安全、无效或无法解析的子页面地址。 */ }
  }
  return links;
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
    // 只接受域名，不接受任何 IPv4/IPv6 字面量：避免环回、私网、链路本地、ULA、IPv4-mapped IPv6 等 Worker SSRF 变体。
    if (
      hostname === "localhost" || hostname.endsWith(".localhost")
      || isIpv4Literal(hostname) || hostname.includes(":")
    ) return false;
    return hostname.length > 0;
  } catch {
    return false;
  }
}

function isIpv4Literal(hostname) {
  const octets = hostname.split(".").map(Number);
  return octets.length === 4 && octets.every((value) => Number.isInteger(value) && value >= 0 && value <= 255);
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
  const rows = await supabaseRequest(env, `/rest/v1/source_capture_candidates?id=eq.${candidateId}&select=workspace_id,status&limit=1`);
  if (!rows[0]) throw new Error("候选不存在。");
  await assertWorkspaceMember(env, rows[0].workspace_id, userId);
  if (rows[0].status !== "pending") throw new Error("只能删除待审核 Candidate，已采纳内容必须从正式证据中处理。");
  await supabaseRequest(env, `/rest/v1/source_capture_candidates?id=eq.${candidateId}`, { method: "DELETE", headers: { Prefer: "return=minimal" } });
}

// 删除整批仅面向待审核 run：级联清理其 raw snapshots、图片元数据和 pending Candidate，绝不触碰正式证据、矩阵或洞察。
async function deleteAuthorizedCaptureRun(env, userId, runId) {
  const runs = await supabaseRequest(env, `/rest/v1/source_capture_runs?id=eq.${encodeURIComponent(runId)}&select=id,workspace_id&limit=1`);
  const run = runs[0];
  if (!run) throw new Error("抓取批次不存在。");
  await assertWorkspaceMember(env, run.workspace_id, userId);
  const candidates = await supabaseRequest(env, `/rest/v1/source_capture_candidates?run_id=eq.${encodeURIComponent(runId)}&select=id,status`);
  if (candidates.some((candidate) => candidate.status !== "pending")) {
    throw new Error("该批次含已处理 Candidate，无法整批删除；请保留正式证据链。");
  }
  await supabaseRequest(env, `/rest/v1/source_capture_runs?id=eq.${encodeURIComponent(runId)}`, { method: "DELETE", headers: { Prefer: "return=minimal" } });
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
  const contentLength = response.headers.get("content-length");
  if (response.status === 204 || contentLength === "0") return null;
  const body = await response.text();
  return body ? JSON.parse(body) : null;
}

function validateEnvironment(env) {
  if (!/^https:\/\//.test(env?.SUPABASE_URL || "") || !env?.SUPABASE_SERVICE_ROLE_KEY) {
    throw new Error("抓取 Worker 缺少受保护的 Supabase 服务端配置。");
  }
}

function safeErrorMessage(error) {
  return String(error?.message || "未知抓取错误").slice(0, 500);
}
