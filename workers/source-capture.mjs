// ============================================================
// 公开来源抓取 Worker：只生成待审核候选，永不写入正式证据、矩阵或洞察。
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
const MANUAL_CAPTURE_COOLDOWN_MS = 5 * 60 * 1000;
const PAGES_PRODUCTION_HOST = "zacclover-competitor.pages.dev";
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export default {
  async scheduled(_event, env, ctx) {
    ctx.waitUntil(runScheduledCapture(env));
  },

  // 手动采集 HTTP 入口：仅接受受信 Pages 来源发起的认证 POST。
  async fetch(request, env, _ctx) {
    return handleManualCaptureRequest(request, env);
  },
};

// 手动采集路由、CORS 与安全错误响应。
export async function handleManualCaptureRequest(request, env) {
  const origin = request.headers.get("Origin");
  const corsHeaders = buildCorsHeaders(origin);
  const pathname = new URL(request.url).pathname;

  if (pathname !== "/manual-capture") {
    return jsonResponse(404, "not_found", "请求的资源不存在。", {}, corsHeaders);
  }
  if (origin && !corsHeaders["Access-Control-Allow-Origin"]) {
    return jsonResponse(403, "origin_not_allowed", "不允许的请求来源。");
  }
  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders });
  }
  if (request.method !== "POST") {
    return jsonResponse(405, "method_not_allowed", "仅支持 POST 请求。", { Allow: "POST" }, corsHeaders);
  }

  try {
    validateManualEnvironment(env);
    const contentType = request.headers.get("Content-Type") || "";
    if (!/^application\/json(?:\s*;|$)/i.test(contentType)) {
      throw new HttpError(415, "unsupported_media_type", "请求正文必须是 JSON。");
    }
    const payload = await readJsonBody(request);
    if (!payload || typeof payload !== "object" || Array.isArray(payload) || !UUID_PATTERN.test(payload.sourceId || "")) {
      throw new HttpError(400, "invalid_request", "sourceId 必须是有效的 UUID。");
    }

    const accessToken = readBearerToken(request.headers.get("Authorization"));
    const user = await verifySupabaseUser(env, accessToken);
    const source = await getSourceById(env, payload.sourceId);
    if (!source) throw new HttpError(404, "source_not_found", "未找到可采集的来源。");
    if (!await isWorkspaceMember(env, source.workspace_id, user.id)) {
      throw new HttpError(403, "workspace_access_denied", "无权采集此工作区的来源。");
    }

    const latestManualRun = await getLatestManualRun(env, source.id);
    const cooldownRemainingMs = getCooldownRemainingMs(latestManualRun?.created_at);
    if (cooldownRemainingMs > 0) {
      throw new HttpError(429, "manual_capture_cooldown", "此来源刚刚手动采集过，请稍后重试。", {
        "Retry-After": String(Math.ceil(cooldownRemainingMs / 1000)),
      });
    }

    const result = await captureSource(source, env, "manual");
    return new Response(JSON.stringify({ ok: true, result }), {
      status: 200,
      headers: { "Content-Type": "application/json; charset=utf-8", ...corsHeaders },
    });
  } catch (error) {
    const safeError = error instanceof HttpError
      ? error
      : new HttpError(500, "internal_error", "手动采集暂时不可用，请稍后重试。");
    return jsonResponse(safeError.status, safeError.code, safeError.publicMessage, safeError.headers, corsHeaders);
  }
}

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
    const isChanged = shouldQueueCandidate(previousSnapshot?.content_hash, snapshot.contentHash);

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
    }, "resolution=ignore-duplicates,return=representation");

    if (isChanged) {
      await insertRecord(env, "source_capture_candidates", {
        id: crypto.randomUUID(),
        workspace_id: source.workspace_id,
        tab_id: source.tab_id,
        competitor_id: source.competitor_id,
        source_id: source.id,
        run_id: run.id,
        snapshot_id: savedSnapshot?.id || previousSnapshot?.id,
        source_url: page.canonicalUrl,
        title: page.title || "检测到公开页面内容变化",
        summary: buildSummary(snapshot.extractedText),
        quoted_text: snapshot.extractedText.slice(0, 1_200),
        content_hash: snapshot.contentHash,
        status: "pending",
      });
    }

    await updateRecord(env, "competitor_sources", source.id, {
      last_fetched_at: new Date().toISOString(),
    });
    await updateRecord(env, "source_capture_runs", run.id, {
      status: "succeeded",
      http_status: page.httpStatus,
      finished_at: new Date().toISOString(),
    });
    return {
      sourceId: source.id,
      runId: run.id,
      candidateQueued: isChanged,
      status: "succeeded",
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

// Supabase 用户认证：用户 JWT 仅发送到 Auth，绝不作为数据库服务角色凭据。
async function verifySupabaseUser(env, accessToken) {
  const response = await fetch(`${env.SUPABASE_URL}/auth/v1/user`, {
    headers: {
      apikey: env.SUPABASE_PUBLISHABLE_KEY,
      Authorization: `Bearer ${accessToken}`,
    },
  });
  if (!response.ok) throw new HttpError(401, "invalid_token", "登录凭据无效或已过期。");
  const user = await response.json();
  if (!user?.id || !UUID_PATTERN.test(user.id)) {
    throw new HttpError(401, "invalid_token", "登录凭据无效或已过期。");
  }
  return user;
}

// 手动采集授权：认证完成后才用 service role 读取单一来源与成员关系。
async function getSourceById(env, sourceId) {
  const records = await supabaseRequest(
    env,
    `/rest/v1/competitor_sources?id=eq.${encodeURIComponent(sourceId)}&select=id,workspace_id,tab_id,competitor_id,url&limit=1`,
  );
  return records[0] || null;
}

async function isWorkspaceMember(env, workspaceId, userId) {
  const records = await supabaseRequest(
    env,
    `/rest/v1/workspace_members?workspace_id=eq.${encodeURIComponent(workspaceId)}&user_id=eq.${encodeURIComponent(userId)}&select=workspace_id&limit=1`,
  );
  return records.length > 0;
}

// 五分钟冷却只查看该来源最近一次 manual 运行的 created_at。
async function getLatestManualRun(env, sourceId) {
  const records = await supabaseRequest(
    env,
    `/rest/v1/source_capture_runs?source_id=eq.${encodeURIComponent(sourceId)}&trigger_type=eq.manual&select=created_at&order=created_at.desc&limit=1`,
  );
  return records[0] || null;
}

export function getCooldownRemainingMs(createdAt, now = Date.now()) {
  const createdAtMs = Date.parse(createdAt || "");
  if (Number.isNaN(createdAtMs)) return 0;
  return Math.max(0, MANUAL_CAPTURE_COOLDOWN_MS - (now - createdAtMs));
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
    };
  } finally {
    clearTimeout(timeout);
  }
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

function validateManualEnvironment(env) {
  validateEnvironment(env);
  if (!env?.SUPABASE_PUBLISHABLE_KEY) {
    throw new Error("抓取 Worker 缺少 Supabase 公开认证配置。");
  }
}

// Pages CORS：精确允许生产域名及其预览子域，绝不回显其他 Origin。
function buildCorsHeaders(origin) {
  const headers = {
    "Access-Control-Allow-Methods": "POST",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
  if (isAllowedPagesOrigin(origin)) headers["Access-Control-Allow-Origin"] = origin;
  return headers;
}

export function isAllowedPagesOrigin(origin) {
  if (!origin) return false;
  try {
    const url = new URL(origin);
    return url.protocol === "https:" && !url.username && !url.password && !url.port &&
      (url.hostname === PAGES_PRODUCTION_HOST || url.hostname.endsWith(`.${PAGES_PRODUCTION_HOST}`)) &&
      url.pathname === "/" && !url.search && !url.hash;
  } catch {
    return false;
  }
}

function readBearerToken(authorization) {
  const match = String(authorization || "").match(/^Bearer ([^\s]+)$/i);
  if (!match) throw new HttpError(401, "authentication_required", "需要有效的 Bearer 登录凭据。");
  return match[1];
}

async function readJsonBody(request) {
  try {
    return await request.json();
  } catch {
    throw new HttpError(400, "invalid_json", "请求正文不是有效的 JSON。");
  }
}

function jsonResponse(status, code, message, extraHeaders = {}, corsHeaders = {}) {
  return new Response(JSON.stringify({ ok: false, error: { code, message } }), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...corsHeaders,
      ...extraHeaders,
    },
  });
}

class HttpError extends Error {
  constructor(status, code, publicMessage, headers = {}) {
    super(publicMessage);
    this.status = status;
    this.code = code;
    this.publicMessage = publicMessage;
    this.headers = headers;
  }
}

function safeErrorMessage(error) {
  return String(error?.message || "未知抓取错误").slice(0, 500);
}
