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
const MAX_ANALYSIS_INPUT_CHARS = 6_000;
const ANALYSIS_RESERVED_TOKENS = 8_000;
const DAILY_AI_REQUEST_LIMIT = 20;
const DAILY_AI_TOKEN_LIMIT = 160_000;
const GEMINI_DEFAULT_MODEL = "gemini-2.5-flash-lite";
const ANALYSIS_SCHEMA_VERSION = "preview_candidate_analysis_v1";
const REQUEST_TIMEOUT_MS = 20_000;
const MANUAL_CAPTURE_COOLDOWN_MS = 5 * 60 * 1000;
const PAGES_PRODUCTION_HOST = "zacclover-competitor.pages.dev";
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const ISO_TIMESTAMP_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})$/;

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
    const observationWindow = validateObservationWindow(payload.observationWindow, new Date());

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

    const result = await captureSource(source, env, "manual", observationWindow);
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
  const plannedAt = new Date();
  const sources = await queryDueSources(env);
  const results = await Promise.allSettled(sources.map((source) => captureSource(source, env, "scheduled", null, plannedAt)));
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

async function captureSource(source, env, triggerType = "scheduled", explicitWindow = null, plannedAt = new Date()) {
  const observationWindow = explicitWindow || await deriveObservationWindow(env, source.id, plannedAt);
  const run = await insertRecord(env, "source_capture_runs", {
    id: crypto.randomUUID(),
    workspace_id: source.workspace_id,
    tab_id: source.tab_id,
    source_id: source.id,
    trigger_type: triggerType,
    status: "running",
    detection_window_start: observationWindow.start,
    detection_window_end: observationWindow.end,
    detection_window_basis: observationWindow.basis,
  });

  try {
    const previousSnapshot = await getLatestSnapshot(env, source.id);
    const page = await fetchPublicSource(source.url);
    const snapshot = await createSnapshot(page.extractedText);
    const isChanged = shouldQueueCandidate(previousSnapshot?.content_hash, snapshot.contentHash);

    const savedSnapshot = await insertRecord(env, "source_capture_snapshots?on_conflict=source_id%2Ccontent_hash", {
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
      const candidate = await insertRecord(env, "source_capture_candidates", {
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
        analysis_status: "unavailable",
        publication_time_status: "unverified",
        detection_window_start: observationWindow.start,
        detection_window_end: observationWindow.end,
        detection_window_basis: observationWindow.basis,
      });
      await enrichCandidateWithAnalysis(env, candidate.id, page, snapshot.extractedText);
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

// 观察窗口：手动显式窗口必须成对、为合法 ISO 时间且不延伸到未来。
export function validateObservationWindow(value, now = new Date()) {
  if (value == null) return null;
  if (!value || typeof value !== "object" || Array.isArray(value) ||
      typeof value.start !== "string" || typeof value.end !== "string") {
    throw new HttpError(400, "invalid_observation_window", "observationWindow 必须同时包含有效的 start 与 end。 ");
  }
  const startMs = ISO_TIMESTAMP_PATTERN.test(value.start) ? Date.parse(value.start) : NaN;
  const endMs = ISO_TIMESTAMP_PATTERN.test(value.end) ? Date.parse(value.end) : NaN;
  if (Number.isNaN(startMs) || Number.isNaN(endMs) || startMs >= endMs || endMs > now.getTime()) {
    throw new HttpError(400, "invalid_observation_window", "观察窗口必须是起点早于终点且终点不晚于当前时间的 ISO 时间。 ");
  }
  return { start: new Date(startMs).toISOString(), end: new Date(endMs).toISOString(), basis: "explicit" };
}

// 定时与未显式指定窗口的手动任务，从上次成功结束时间观察到本次计划时间。
export async function deriveObservationWindow(env, sourceId, plannedAt) {
  const records = await supabaseRequest(
    env,
    `/rest/v1/source_capture_runs?source_id=eq.${encodeURIComponent(sourceId)}&status=eq.succeeded&select=finished_at&order=finished_at.desc&limit=1`,
  );
  const previous = records[0]?.finished_at;
  return {
    start: previous && Date.parse(previous) < plannedAt.getTime() ? new Date(previous).toISOString() : null,
    end: plannedAt.toISOString(),
    basis: previous && Date.parse(previous) < plannedAt.getTime() ? "prior_success" : "initial_observation",
  };
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
      .replace(/<(nav|header|footer|aside|form)\b[^>]*>[\s\S]*?<\/\1>/gi, " ")
      .replace(/<\/(?:p|div|main|article|section|li|h[1-6]|tr)>/gi, "\n")
      .replace(/<[^>]+>/g, " ")
      .replace(/[^\S\r\n]+/g, " ")
      .replace(/\n\s*\n+/g, "\n")
      .trim(),
  ).slice(0, MAX_EXTRACTED_TEXT_LENGTH);
}

// AI 输入清洗：去除重复行与常见导航短语，并在 Unicode 字符边界截断到 6000 字符。
export function prepareAnalysisInput(text) {
  const seen = new Set();
  const navigation = /^(home|menu|search|sign in|log in|subscribe|首页|菜单|搜索|登录|订阅|返回顶部)$/i;
  const lines = String(text || "").split(/\n+/).map((line) => line.replace(/\s+/g, " ").trim())
    .filter((line) => {
      if (!line || navigation.test(line)) return false;
      const key = line.toLocaleLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  return Array.from(lines.join("\n")).slice(0, MAX_ANALYSIS_INPUT_CHARS).join("");
}

// Preview-only 候选分析：任何配置、额度、网络或校验失败都保持候选成功且仅记录 unavailable。
export async function enrichCandidateWithAnalysis(env, candidateId, page, extractedText) {
  if (!env?.GEMINI_API_KEY) return;
  const model = String(env.GEMINI_MODEL || GEMINI_DEFAULT_MODEL);
  if (!/^gemini-[a-z0-9.-]*flash-lite(?:-[a-z0-9.-]+)?$/i.test(model)) return;
  const input = prepareAnalysisInput(extractedText);
  if (!input) return;

  try {
    const reserved = await reserveAnalysisBudget(env);
    if (!reserved) return;
    const analysis = await requestGeminiAnalysis(env, model, page, input);
    await updateRecord(env, "source_capture_candidates", candidateId, {
      analysis_status: "available",
      analysis,
      analysis_model: model,
      analysis_schema_version: ANALYSIS_SCHEMA_VERSION,
      analysis_input_chars: Array.from(input).length,
      analysis_reserved_tokens: ANALYSIS_RESERVED_TOKENS,
      analyzed_at: new Date().toISOString(),
      publication_time_status: analysis.publication_time.status,
      published_at: analysis.publication_time.status === "verified" ? analysis.publication_time.value : null,
    });
  } catch {
    // 故意吞掉供应商与额度细节；抓取结果和候选不能因可选分析失败而失败。
  }
}

async function reserveAnalysisBudget(env) {
  const result = await supabaseRequest(env, "/rest/v1/rpc/reserve_source_capture_ai_budget", {
    method: "POST",
    body: JSON.stringify({
      requested_tokens: ANALYSIS_RESERVED_TOKENS,
      daily_request_limit: DAILY_AI_REQUEST_LIMIT,
      daily_token_limit: DAILY_AI_TOKEN_LIMIT,
    }),
  });
  return result === true;
}

// Gemini 使用严格响应 Schema；密钥只置于服务端请求头，不写入 URL、数据库或响应。
async function requestGeminiAnalysis(env, model, page, input) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-goog-api-key": env.GEMINI_API_KEY },
        signal: controller.signal,
        body: JSON.stringify({
          systemInstruction: { parts: [{ text: "你是严谨的竞品研究助手。只根据输入页面作答。所有生成字段必须使用简体中文，表达简洁；推断和竞争影响必须明确标注。不得补充、猜测或伪造事实、引文和发布时间。原文引文保持页面原始语言，并附简体中文释义。无法确认发布时间时标为 not_found 或 unverified，value 必须为 null。" }] },
          contents: [{ role: "user", parts: [{ text: `来源标题：${page.title || "未提供"}\n来源 URL：${page.canonicalUrl}\n清洗后的页面正文：\n${input}` }] }],
          generationConfig: {
            temperature: 0,
            maxOutputTokens: 1800,
            responseMimeType: "application/json",
            responseJsonSchema: analysisJsonSchema(),
          },
        }),
      },
    );
    if (!response.ok) throw new Error("analysis unavailable");
    const payload = await response.json();
    const raw = payload?.candidates?.[0]?.content?.parts?.[0]?.text;
    if (typeof raw !== "string") throw new Error("analysis unavailable");
    return validateAnalysis(JSON.parse(raw), input);
  } finally {
    clearTimeout(timeout);
  }
}

function analysisJsonSchema() {
  return {
    type: "object",
    additionalProperties: false,
    required: ["conclusion", "facts", "inference", "competitive_impact", "quotes", "confidence", "publication_time"],
    properties: {
      conclusion: { type: "string" },
      facts: { type: "array", minItems: 2, maxItems: 4, items: { type: "string" } },
      inference: { type: "object", additionalProperties: false, required: ["label", "text"], properties: { label: { type: "string", enum: ["推断"] }, text: { type: "string" } } },
      competitive_impact: { type: "object", additionalProperties: false, required: ["label", "text"], properties: { label: { type: "string", enum: ["竞争影响"] }, text: { type: "string" } } },
      quotes: { type: "array", minItems: 2, maxItems: 3, items: { type: "object", additionalProperties: false, required: ["original", "chinese_gloss"], properties: { original: { type: "string" }, chinese_gloss: { type: "string" } } } },
      confidence: { type: "string", enum: ["high", "medium", "low"] },
      publication_time: { type: "object", additionalProperties: false, required: ["status", "value", "source_text"], properties: { status: { type: "string", enum: ["verified", "not_found", "unverified"] }, value: { type: "string", nullable: true }, source_text: { type: "string", nullable: true } } },
    },
  };
}

// 输出二次校验：即使模型声称符合 Schema，引文和已验证发布时间也必须能回指输入原文。
export function validateAnalysis(value, input) {
  if (!value || typeof value !== "object" || typeof value.conclusion !== "string" || !value.conclusion.trim() ||
      !Array.isArray(value.facts) || value.facts.length < 2 || value.facts.length > 4 || !value.facts.every((fact) => typeof fact === "string" && fact.trim()) ||
      !Array.isArray(value.quotes) || value.quotes.length < 2 || value.quotes.length > 3 ||
      !value.quotes.every((quote) => typeof quote?.original === "string" && quote.original.length > 0 && input.includes(quote.original) && typeof quote.chinese_gloss === "string") ||
      !["high", "medium", "low"].includes(value.confidence) || value.inference?.label !== "推断" ||
      typeof value.inference?.text !== "string" || value.competitive_impact?.label !== "竞争影响" ||
      typeof value.competitive_impact?.text !== "string" || !["verified", "not_found", "unverified"].includes(value.publication_time?.status)) {
    throw new Error("analysis unavailable");
  }
  if (value.publication_time.status === "verified") {
    if (typeof value.publication_time.value !== "string" || !ISO_TIMESTAMP_PATTERN.test(value.publication_time.value) ||
        Number.isNaN(Date.parse(value.publication_time.value)) ||
        typeof value.publication_time.source_text !== "string" || !input.includes(value.publication_time.source_text)) {
      throw new Error("analysis unavailable");
    }
    value.publication_time.value = new Date(value.publication_time.value).toISOString();
  } else {
    value.publication_time.value = null;
  }
  return value;
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
