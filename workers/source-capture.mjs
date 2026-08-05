// ============================================================
// 公开来源抓取 Worker：只生成待审核候选，永不写入正式证据、矩阵或洞察。
// 仅由受认证的手动 POST 运行；服务端密钥仅存在于 Worker 环境变量。
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
const GLM_DEFAULT_MODEL = "glm-4.5-flash";
const GLM_CHAT_COMPLETIONS_ENDPOINT = "https://api.z.ai/api/paas/v4/chat/completions";
const GEMINI_MODELS_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models";
const ANALYSIS_SCHEMA_VERSION = "preview_candidate_analysis_v2";
const REQUEST_TIMEOUT_MS = 20_000;
const MANUAL_CAPTURE_COOLDOWN_MS = 5 * 60 * 1000;
const MAX_UPDATE_CHILD_PAGES = 20;
const MAX_CANDIDATE_IMAGES = 3;
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const CANDIDATE_ATTACHMENTS_BUCKET = "candidate-attachments";
const ALLOWED_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp", "image/gif"]);
const SEMANTIC_SOURCE_TYPES = new Set(["changelog", "release_notes"]);
const PAGES_PRODUCTION_HOST = "zacclover-competitor.pages.dev";
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const ISO_TIMESTAMP_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})$/;
const SIMPLIFIED_CHINESE_TEXT_PATTERN = /[\u3400-\u9fff]/u;
const LATIN_TEXT_PATTERN = /[A-Za-z]/;
const FEATURE_FALLBACK = Object.freeze({
  title: "待分析功能更新",
  summary: "发现一项发布时间符合观察窗口的功能更新，具体内容请查看来源页面。",
});
const PAGE_FALLBACK = Object.freeze({
  title: "待分析页面更新",
  summary: "检测到公开页面内容发生变化，具体内容请查看来源页面。",
});

export default {
  async scheduled(_event, env, ctx) {
    ctx.waitUntil(runScheduledCapture(env));
  },

  // 手动采集 HTTP 入口：仅接受受信 Pages 来源发起的认证 POST。
  async fetch(request, env, ctx) {
    return handleManualCaptureRequest(request, env, ctx);
  },
};

// 手动采集路由、CORS 与安全错误响应。
export async function handleManualCaptureRequest(request, env, ctx = null) {
  const origin = request.headers.get("Origin");
  const corsHeaders = buildCorsHeaders(origin);
  const pathname = new URL(request.url).pathname;

  const attachmentGetMatch = pathname.match(/^\/candidate-attachments\/([0-9a-f-]+)\/([0-9a-f-]+)$/i);
  if (attachmentGetMatch) {
    return handleCandidateAttachmentGet(request, env, attachmentGetMatch[1], attachmentGetMatch[2], corsHeaders);
  }
  const attachmentDeleteMatch = pathname.match(/^\/candidate-attachments\/([0-9a-f-]+)$/i);
  if (attachmentDeleteMatch) {
    return handleCandidateAttachmentDelete(request, env, attachmentDeleteMatch[1], corsHeaders);
  }
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

    const result = await captureSource(source, env, "manual", observationWindow, new Date(), ctx);
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

// 私有候选附件读取：候选工作区授权与附件归属均通过后，才以服务角色读取对象并返回安全位图。
async function handleCandidateAttachmentGet(request, env, candidateId, attachmentId, corsHeaders) {
  const origin = request.headers.get("Origin");
  if (origin && !corsHeaders["Access-Control-Allow-Origin"]) {
    return jsonResponse(403, "origin_not_allowed", "不允许的请求来源。");
  }
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });
  if (request.method !== "GET") {
    return jsonResponse(405, "method_not_allowed", "仅支持 GET 请求。", { Allow: "GET" }, corsHeaders);
  }
  try {
    validateManualEnvironment(env);
    if (!UUID_PATTERN.test(candidateId) || !UUID_PATTERN.test(attachmentId)) {
      throw new HttpError(400, "invalid_attachment_id", "候选或附件 ID 无效。");
    }
    const user = await verifySupabaseUser(env, readBearerToken(request.headers.get("Authorization")));
    const candidates = await supabaseRequest(env,
      `/rest/v1/source_capture_candidates?id=eq.${encodeURIComponent(candidateId)}&select=id,workspace_id&limit=1`);
    const candidate = candidates[0];
    if (!candidate) throw new HttpError(404, "candidate_not_found", "未找到候选。");
    if (!await isWorkspaceMember(env, candidate.workspace_id, user.id)) {
      throw new HttpError(403, "workspace_access_denied", "无权读取此工作区的候选附件。");
    }
    const attachments = await supabaseRequest(env,
      `/rest/v1/candidate_attachments?id=eq.${encodeURIComponent(attachmentId)}&candidate_id=eq.${encodeURIComponent(candidateId)}` +
      `&workspace_id=eq.${encodeURIComponent(candidate.workspace_id)}&select=id,object_path,media_type,byte_size&limit=1`);
    const attachment = attachments[0];
    if (!attachment) throw new HttpError(404, "attachment_not_found", "未找到候选附件。");
    if (!ALLOWED_IMAGE_TYPES.has(String(attachment.media_type || "").toLowerCase()) ||
        !Number.isInteger(attachment.byte_size) || attachment.byte_size < 0 || attachment.byte_size > MAX_IMAGE_BYTES) {
      throw new HttpError(415, "unsafe_attachment", "附件类型或大小不受支持。");
    }
    const object = await retrieveStorageObject(env, attachment.object_path);
    if (object.mediaType !== attachment.media_type.toLowerCase() || object.bytes.byteLength !== attachment.byte_size) {
      throw new HttpError(415, "unsafe_attachment", "附件类型或大小不受支持。");
    }
    return new Response(object.bytes, {
      status: 200,
      headers: {
        "Content-Type": object.mediaType,
        "Content-Length": String(object.bytes.byteLength),
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
        ...corsHeaders,
      },
    });
  } catch (error) {
    const safeError = error instanceof HttpError ? error : new HttpError(500, "internal_error", "候选附件暂时不可用。");
    return jsonResponse(safeError.status, safeError.code, safeError.publicMessage, safeError.headers, corsHeaders);
  }
}

// 候选删除边界：认证并确认工作区成员后，先清理私有对象，再删除附件记录与候选本身。
async function handleCandidateAttachmentDelete(request, env, candidateId, corsHeaders) {
  const origin = request.headers.get("Origin");
  if (origin && !corsHeaders["Access-Control-Allow-Origin"]) {
    return jsonResponse(403, "origin_not_allowed", "不允许的请求来源。");
  }
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });
  if (request.method !== "DELETE") {
    return jsonResponse(405, "method_not_allowed", "仅支持 DELETE 请求。", { Allow: "DELETE" }, corsHeaders);
  }
  try {
    validateManualEnvironment(env);
    if (!UUID_PATTERN.test(candidateId)) throw new HttpError(400, "invalid_candidate_id", "候选 ID 无效。");
    const user = await verifySupabaseUser(env, readBearerToken(request.headers.get("Authorization")));
    const records = await supabaseRequest(env,
      `/rest/v1/source_capture_candidates?id=eq.${encodeURIComponent(candidateId)}&select=id,workspace_id&limit=1`);
    const candidate = records[0];
    if (!candidate) throw new HttpError(404, "candidate_not_found", "未找到候选。");
    if (!await isWorkspaceMember(env, candidate.workspace_id, user.id)) {
      throw new HttpError(403, "workspace_access_denied", "无权删除此工作区的候选。");
    }
    const attachments = await supabaseRequest(env,
      `/rest/v1/candidate_attachments?candidate_id=eq.${encodeURIComponent(candidateId)}&select=object_path`);
    for (const attachment of attachments) await deleteStorageObject(env, attachment.object_path);
    await deleteRecords(env, "candidate_attachments", "candidate_id", candidateId);
    await deleteRecords(env, "source_capture_candidates", "id", candidateId);
    return new Response(JSON.stringify({ ok: true, candidateId }), {
      status: 200, headers: { "Content-Type": "application/json; charset=utf-8", ...corsHeaders },
    });
  } catch (error) {
    const safeError = error instanceof HttpError ? error : new HttpError(500, "internal_error", "候选删除暂时不可用。");
    return jsonResponse(safeError.status, safeError.code, safeError.publicMessage, safeError.headers, corsHeaders);
  }
}

// 定时事件是显式禁用边界：不读取来源、不抓取、不写入任何记录。
export async function runScheduledCapture(_env) {
  return { disabled: true, inspected: 0, succeeded: 0, failed: 0 };
}

async function captureSource(source, env, triggerType = "scheduled", explicitWindow = null, plannedAt = new Date(), ctx = null) {
  const analysisRequestCache = {};
  const deferredAttachmentTasks = [];
  const deferredAnalysisTasks = [];
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
    const isSemanticSource = supportsUpdateSubpageDiscovery(source.source_type);
    const isChanged = shouldQueueCandidate(previousSnapshot?.content_hash, snapshot.contentHash);
    let candidateQueued = false;
    let candidateCount = 0;

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

    if (isSemanticSource) {
      const discovery = await discoverEligibleUpdates(page, observationWindow);
      for (const entry of discovery.entries) {
        const entryHash = await hashSelectedEntries([entry]);
        const existingCandidate = await getExistingCandidate(env, source.workspace_id, source.id, entryHash);
        if (existingCandidate) {
          if (shouldRetryExistingCandidate(triggerType, existingCandidate)) {
            if (!await candidateHasAttachments(env, existingCandidate.workspace_id, existingCandidate.id)) {
              scheduleCandidateImageAttachments(deferredAttachmentTasks, env, existingCandidate, entry);
            }
            scheduleCandidateAnalysis(deferredAnalysisTasks, env, existingCandidate.id, {
              title: entry.title, canonicalUrl: entry.url,
            }, entry.extractedText, analysisRequestCache);
          }
          continue;
        }

        const candidate = await insertRecord(env, "source_capture_candidates?on_conflict=source_id%2Ccontent_hash", {
          id: crypto.randomUUID(), workspace_id: source.workspace_id, tab_id: source.tab_id,
          competitor_id: source.competitor_id, source_id: source.id, run_id: run.id,
          snapshot_id: savedSnapshot?.id || previousSnapshot?.id, source_url: entry.url,
          title: FEATURE_FALLBACK.title, summary: FEATURE_FALLBACK.summary, quoted_text: "",
          content_hash: entryHash, status: "pending", analysis_status: "unavailable",
          publication_time_status: "verified", published_at: entry.publishedAt,
          detection_window_start: observationWindow.start, detection_window_end: observationWindow.end,
          detection_window_basis: observationWindow.basis,
          selected_entries: [{ url: entry.url, title: entry.title, publishedAt: entry.publishedAt, dateSource: entry.dateSource }],
          excluded_missing_date_count: discovery.missingDateCount,
        }, "resolution=ignore-duplicates,return=representation");
        if (!candidate) continue;
        candidateQueued = true;
        candidateCount += 1;
        scheduleCandidateImageAttachments(deferredAttachmentTasks, env, candidate, entry);
        scheduleCandidateAnalysis(deferredAnalysisTasks, env, candidate.id, {
          title: entry.title, canonicalUrl: entry.url,
        }, entry.extractedText, analysisRequestCache);
      }
    } else if (isChanged) {
      const candidate = await insertRecord(env, "source_capture_candidates", {
        id: crypto.randomUUID(),
        workspace_id: source.workspace_id,
        tab_id: source.tab_id,
        competitor_id: source.competitor_id,
        source_id: source.id,
        run_id: run.id,
        snapshot_id: savedSnapshot?.id || previousSnapshot?.id,
        source_url: page.canonicalUrl,
        title: PAGE_FALLBACK.title,
        summary: PAGE_FALLBACK.summary,
        quoted_text: "",
        content_hash: snapshot.contentHash,
        status: "pending",
        analysis_status: "unavailable",
        publication_time_status: "unverified",
        detection_window_start: observationWindow.start,
        detection_window_end: observationWindow.end,
        detection_window_basis: observationWindow.basis,
      });
      candidateCount = candidate ? 1 : 0;
      if (candidate) scheduleCandidateAnalysis(deferredAnalysisTasks, env, candidate.id, page, snapshot.extractedText, analysisRequestCache);
    }

    await updateRecord(env, "competitor_sources", source.id, {
      last_fetched_at: new Date().toISOString(),
    });
    await updateRecord(env, "source_capture_runs", run.id, {
      status: "succeeded",
      http_status: page.httpStatus,
      finished_at: new Date().toISOString(),
    });
    const optionalEnrichmentWork = Promise.allSettled([
      ...deferredAttachmentTasks.map((task) => task()),
      ...deferredAnalysisTasks.map((task) => task()),
    ]);
    if (typeof ctx?.waitUntil === "function") ctx.waitUntil(optionalEnrichmentWork);
    else await optionalEnrichmentWork;
    return {
      sourceId: source.id,
      runId: run.id,
      candidateQueued: isSemanticSource ? candidateQueued : isChanged,
      candidateCount,
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

// 可选 AI 分析在 Candidate 已创建且 run 成功后执行，不能拖慢手动抓取响应。
function scheduleCandidateAnalysis(deferredAnalysisTasks, env, candidateId, page, extractedText, analysisRequestCache) {
  deferredAnalysisTasks.push(() => enrichCandidateWithAnalysis(env, candidateId, page, extractedText, analysisRequestCache));
}

// 图片是可选私有附件：Candidate 已创建后才在请求生命周期外补抓，不能拖慢手动抓取响应。
function scheduleCandidateImageAttachments(deferredAttachmentTasks, env, candidate, entry) {
  deferredAttachmentTasks.push(() => attachCandidateImages(env, candidate, entry));
}

// 仅变更日志与发布说明启用子页语义发现，其他来源继续使用单页哈希。
export function supportsUpdateSubpageDiscovery(sourceType) {
  return SEMANTIC_SOURCE_TYPES.has(sourceType);
}

// 仅用户触发的手动采集可重试尚未分析的待审核候选。
export function shouldRetryExistingCandidate(triggerType, candidate) {
  return triggerType === "manual" && candidate?.status === "pending" &&
    candidate.analysis_status === "unavailable";
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
    `/rest/v1/competitor_sources?id=eq.${encodeURIComponent(sourceId)}&select=id,workspace_id,tab_id,competitor_id,source_type,url&limit=1`,
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
      html,
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
    if (url.protocol !== "https:" || url.username || url.password || url.port) return false;
    const hostname = url.hostname.toLowerCase();
    if (hostname === "localhost" || hostname.endsWith(".localhost") || hostname === "0" ||
        hostname.endsWith(".local") || hostname.includes(":") || isPrivateIpv4(hostname)) {
      return false;
    }
    return hostname.length > 0;
  } catch {
    return false;
  }
}

// 更新子页发现规则：只读取非导航区的显式 <a href>，且链接必须与索引同源、
// 在索引路径之下多一层，或位于 changelog/release-notes/releases/updates 路径下。
// 不猜测 URL、不跟随子页链接，因此深度恒为 1；按文档顺序去重并硬性限制 20 页。
export function discoverUpdateLinks(indexHtml, indexUrl) {
  const base = new URL(canonicalizeSourceUrl(indexUrl));
  const baseSegments = pathSegments(base.pathname);
  const updateMarker = /^(?:changelog|release-notes|releases|updates)$/i;
  const stripped = String(indexHtml || "")
    .replace(/<(nav|header|footer|aside|form)\b[^>]*>[\s\S]*?<\/\1>/gi, " ")
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, " ");
  const links = [];
  const seen = new Set();
  for (const match of stripped.matchAll(/<a\b[^>]*\bhref\s*=\s*(?:"([^"]+)"|'([^']+)')[^>]*>/gi)) {
    if (links.length >= MAX_UPDATE_CHILD_PAGES) break;
    try {
      const url = new URL(decodeHtmlEntities(match[1] || match[2]), base);
      url.hash = "";
      const segments = pathSegments(url.pathname);
      const belowIndex = baseSegments.length > 0 && segments.length === baseSegments.length + 1 &&
        baseSegments.every((segment, index) => segment === segments[index]);
      const markerIndex = segments.findIndex((segment) => updateMarker.test(segment));
      const belowMarker = markerIndex >= 0 && segments.length === markerIndex + 2;
      if (url.origin !== base.origin || !isSafePublicSourceUrl(url.toString()) ||
          url.toString() === base.toString() || (!belowIndex && !belowMarker)) continue;
      const canonical = canonicalizeSourceUrl(url.toString());
      if (!seen.has(canonical)) {
        seen.add(canonical);
        links.push(canonical);
      }
    } catch {
      // 无效或非 HTTP URL 不是候选子页。
    }
  }
  return links;
}

function pathSegments(pathname) {
  return pathname.split("/").filter(Boolean).map((value) => decodeURIComponent(value).toLocaleLowerCase());
}

// 声明日期仅接受文档元数据、JSON-LD datePublished 或 <time datetime>；
// 普通正文中看似日期的字符不足以验证发布日期，避免将导航或历史日期误当发布日期。
export function extractDeclaredUpdateDate(html) {
  const candidates = [
    ...String(html || "").matchAll(/<meta\b[^>]*(?:property|name)\s*=\s*["'](?:article:published_time|datePublished|publish(?:ed)?_?date)["'][^>]*content\s*=\s*["']([^"']+)["'][^>]*>/gi),
    ...String(html || "").matchAll(/<meta\b[^>]*content\s*=\s*["']([^"']+)["'][^>]*(?:property|name)\s*=\s*["'](?:article:published_time|datePublished|publish(?:ed)?_?date)["'][^>]*>/gi),
    ...String(html || "").matchAll(/<time\b[^>]*datetime\s*=\s*["']([^"']+)["'][^>]*>/gi),
    ...String(html || "").matchAll(/["']datePublished["']\s*:\s*["']([^"']+)["']/gi),
  ];
  for (const match of candidates) {
    const raw = match[1].trim();
    const parsed = parseDeclaredDate(raw);
    if (parsed) return { publishedAt: parsed, dateSource: raw };
  }
  return null;
}

function parseDeclaredDate(raw) {
  if (!/^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,3})?)?(?:Z|[+-]\d{2}:?\d{2}))?$/.test(raw)) return null;
  const value = /^\d{4}-\d{2}-\d{2}$/.test(raw) ? `${raw}T00:00:00.000Z` : raw;
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? null : new Date(parsed).toISOString();
}

export async function discoverEligibleUpdates(indexPage, observationWindow, fetchImpl = fetch) {
  const links = discoverUpdateLinks(indexPage.html, indexPage.canonicalUrl);
  const entries = [];
  let missingDateCount = 0;
  const startMs = Date.parse(observationWindow?.start || "");
  const endMs = Date.parse(observationWindow?.end || "");
  for (const url of links) {
    const page = await fetchPublicSource(url, fetchImpl);
    const declared = extractDeclaredUpdateDate(page.html);
    if (!declared) {
      missingDateCount += 1;
      continue;
    }
    const publishedMs = Date.parse(declared.publishedAt);
    if (!Number.isNaN(startMs) && !Number.isNaN(endMs) && publishedMs >= startMs && publishedMs <= endMs) {
      entries.push({
        url: page.canonicalUrl,
        title: page.title || "产品更新",
        ...declared,
        quotedText: page.extractedText.slice(0, 1_200),
        extractedText: page.extractedText,
        html: page.html,
        contentHash: (await createSnapshot(page.extractedText)).contentHash,
      });
    }
  }
  entries.sort((a, b) => a.publishedAt.localeCompare(b.publishedAt) || a.url.localeCompare(b.url));
  return { entries, missingDateCount };
}

export async function hashSelectedEntries(entries) {
  const identity = entries.map(({ url, publishedAt, contentHash = "" }) => ({ url, publishedAt, contentHash }))
    .sort((a, b) => a.url.localeCompare(b.url) || a.publishedAt.localeCompare(b.publishedAt));
  return (await createSnapshot(JSON.stringify(identity))).contentHash;
}

// 候选图片发现：只接受当前更新子页 HTML 中显式 img[src] 的同源 HTTPS 位图地址。
export function discoverFeatureImageUrls(html, pageUrl) {
  const base = new URL(canonicalizeSourceUrl(pageUrl));
  const cleaned = String(html || "").replace(/<(script|iframe|style|noscript)\b[^>]*>[\s\S]*?<\/\1>/gi, " ");
  const urls = [];
  const seen = new Set();
  for (const match of cleaned.matchAll(/<img\b[^>]*\bsrc\s*=\s*(?:"([^"]+)"|'([^']+)')[^>]*>/gi)) {
    if (urls.length >= MAX_CANDIDATE_IMAGES) break;
    try {
      const url = new URL(decodeHtmlEntities(match[1] || match[2]), base);
      url.hash = "";
      if (url.origin !== base.origin || !isSafePublicSourceUrl(url.toString()) ||
          !/\.(?:jpe?g|png|webp|gif)$/i.test(url.pathname)) continue;
      const canonical = url.toString();
      if (!seen.has(canonical)) { seen.add(canonical); urls.push(canonical); }
    } catch {
      // 无效、data 或非 HTTPS 图片地址直接忽略。
    }
  }
  return urls;
}

// 图片下载：手动处理重定向并在读取前后校验 MIME 与 5MB 上限。
export async function fetchFeatureImage(imageUrl, pageUrl, fetchImpl = fetch) {
  const image = new URL(imageUrl);
  const page = new URL(pageUrl);
  if (image.origin !== page.origin || !isSafePublicSourceUrl(image.toString()) ||
      !/\.(?:jpe?g|png|webp|gif)$/i.test(image.pathname)) throw new Error("图片来源不安全。");
  const response = await fetchImpl(image.toString(), {
    headers: { Accept: "image/jpeg,image/png,image/webp,image/gif" }, redirect: "manual",
  });
  if (response.status >= 300 && response.status < 400) throw new Error("图片重定向被拒绝。");
  if (!response.ok) throw new Error(`图片返回 HTTP ${response.status}。`);
  const mediaType = (response.headers.get("content-type") || "").split(";", 1)[0].trim().toLowerCase();
  if (!ALLOWED_IMAGE_TYPES.has(mediaType)) throw new Error("图片 MIME 类型不受支持。");
  const declaredSize = Number(response.headers.get("content-length"));
  if (Number.isFinite(declaredSize) && declaredSize > MAX_IMAGE_BYTES) throw new Error("图片超过大小限制。");
  const bytes = new Uint8Array(await response.arrayBuffer());
  if (bytes.byteLength > MAX_IMAGE_BYTES) throw new Error("图片超过大小限制。");
  return { bytes, mediaType, byteSize: bytes.byteLength, redirectMode: "manual" };
}

// 私有 Storage 上传始终使用 Worker service role，绝不生成公开或签名 URL。
export async function uploadCandidateAttachment(env, objectPath, bytes, mediaType, fetchImpl = fetch) {
  const response = await fetchImpl(`${env.SUPABASE_URL}/storage/v1/object/${CANDIDATE_ATTACHMENTS_BUCKET}/${objectPath}`, {
    method: "POST",
    headers: { apikey: env.SUPABASE_SERVICE_ROLE_KEY, Authorization: `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
      "Content-Type": mediaType, "x-upsert": "false" },
    body: bytes,
  });
  if (!response.ok) throw new Error(`附件存储返回 HTTP ${response.status}。`);
}

async function attachCandidateImages(env, candidate, entry) {
  const urls = discoverFeatureImageUrls(entry.html, entry.url);
  for (let index = 0; index < urls.length; index += 1) {
    let objectPath = null;
    let uploaded = false;
    try {
      const image = await fetchFeatureImage(urls[index], entry.url);
      const extension = image.mediaType === "image/jpeg" ? "jpg" : image.mediaType.split("/")[1];
      objectPath = `${candidate.id}/${index + 1}.${extension}`;
      await uploadCandidateAttachment(env, objectPath, image.bytes, image.mediaType);
      uploaded = true;
      await insertRecord(env, "candidate_attachments", {
        id: crypto.randomUUID(), candidate_id: candidate.id, workspace_id: candidate.workspace_id,
        source_url: urls[index], object_path: objectPath, media_type: image.mediaType,
        byte_size: image.byteSize, created_at: new Date().toISOString(),
      });
    } catch {
      if (uploaded && objectPath) {
        try { await deleteStorageObject(env, objectPath); } catch { /* 后续候选删除仍保持可重试。 */ }
      }
      // 单张图片失败不影响独立候选创建或其余图片。
    }
  }
}

// 语义候选去重与重试严格限定在当前工作区和来源，避免跨来源更新候选。
async function getExistingCandidate(env, workspaceId, sourceId, contentHash) {
  const records = await supabaseRequest(env,
    `/rest/v1/source_capture_candidates?workspace_id=eq.${encodeURIComponent(workspaceId)}` +
    `&source_id=eq.${encodeURIComponent(sourceId)}&content_hash=eq.${encodeURIComponent(contentHash)}` +
    "&select=id,workspace_id,status,analysis_status&limit=1");
  return records[0] || null;
}

// 已有任一合规附件时不重复上传；完全缺失时才从同页重新尝试。
async function candidateHasAttachments(env, workspaceId, candidateId) {
  const records = await supabaseRequest(env,
    `/rest/v1/candidate_attachments?workspace_id=eq.${encodeURIComponent(workspaceId)}` +
    `&candidate_id=eq.${encodeURIComponent(candidateId)}&select=id&limit=1`);
  return records.length > 0;
}

function isPrivateIpv4(hostname) {
  const octets = hostname.split(".").map(Number);
  if (octets.length !== 4 || octets.some((value) => !Number.isInteger(value) || value < 0 || value > 255)) {
    return false;
  }
  const [first, second] = octets;
  return first === 0 || first === 10 || first === 100 && second >= 64 && second <= 127 ||
    first === 127 || first === 169 && second === 254 || first === 172 && second >= 16 && second <= 31 ||
    first === 192 && (second === 0 || second === 168) || first === 198 && (second === 18 || second === 19) ||
    first >= 224;
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
export async function enrichCandidateWithAnalysis(env, candidateId, page, extractedText, analysisRequestCache = {}) {
  if (!env?.ZAI_API_KEY && !env?.GEMINI_API_KEY) {
    logAnalysisUnavailable("missing_model_config");
    return;
  }
  const configuredModel = String(env.GEMINI_MODEL || GEMINI_DEFAULT_MODEL);
  if (env?.GEMINI_API_KEY && !/^gemini-[a-z0-9.-]*flash-lite(?:-[a-z0-9.-]+)?$/i.test(configuredModel)) {
    logAnalysisUnavailable("invalid_model_config");
    return;
  }
  const input = prepareAnalysisInput(extractedText);
  if (!input) {
    logAnalysisUnavailable("empty_input");
    return;
  }

  let reserved;
  try {
    reserved = await reserveAnalysisBudget(env);
  } catch {
    logAnalysisUnavailable("budget_unavailable");
    return;
  }
  if (!reserved) {
    logAnalysisUnavailable("budget_unavailable");
    return;
  }

  try {
    let model;
    let analysis;
    let glmError = null;
    if (env?.ZAI_API_KEY) {
      try {
        analysis = await requestGlmAnalysis(env, page, input);
        model = GLM_DEFAULT_MODEL;
      } catch (error) {
        if (!(error instanceof AnalysisUnavailableError)) throw error;
        logAnalysisProviderFallback("glm", error.reason, error.httpStatus);
        glmError = error;
      }
    }
    if (!analysis && env?.GEMINI_API_KEY) {
      analysisRequestCache.modelsPromise ||= discoverGeminiFlashLiteModels(env);
      const models = await analysisRequestCache.modelsPromise;
      for (const candidateModel of models) {
        try {
          analysis = await requestGeminiAnalysis(env, candidateModel, page, input);
          model = candidateModel;
          break;
        } catch (error) {
          if (!(error instanceof AnalysisUnavailableError) || error.httpStatus !== 404) throw error;
        }
      }
    }
    if (!analysis) throw glmError || new AnalysisUnavailableError("flash_lite_models_unavailable");
    await updateRecord(env, "source_capture_candidates", candidateId, {
      title: analysis.feature_title,
      summary: analysis.feature_summary,
      quoted_text: "",
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
  } catch (error) {
    if (error instanceof AnalysisUnavailableError) {
      logAnalysisUnavailable(error.reason, error.httpStatus);
    } else {
      logAnalysisUnavailable("provider_request_failed");
    }
    // 故意吞掉供应商与额度细节；抓取结果和候选不能因可选分析失败而失败。
  }
}

// Gemini 模型发现：仅在本次候选分析请求内读取并筛选支持 generateContent 的稳定 Flash-Lite。
async function discoverGeminiFlashLiteModels(env) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(GEMINI_MODELS_ENDPOINT, {
      headers: { "x-goog-api-key": env.GEMINI_API_KEY },
      signal: controller.signal,
    });
    if (!response.ok) throw new AnalysisUnavailableError("model_discovery_unavailable", response.status);
    let payload;
    try {
      payload = await response.json();
    } catch {
      throw new AnalysisUnavailableError("model_discovery_unavailable");
    }
    const models = selectGeminiFlashLiteModels(payload?.models);
    if (!models.length) throw new AnalysisUnavailableError("flash_lite_model_unavailable");
    return models;
  } catch (error) {
    if (error instanceof AnalysisUnavailableError) throw error;
    throw new AnalysisUnavailableError("model_discovery_unavailable");
  } finally {
    clearTimeout(timeout);
  }
}

// Gemini 模型选择：首选 2.5 Flash-Lite，其余仅允许无 preview/experimental/latest 标签的稳定版本。
export function selectGeminiFlashLiteModel(models) {
  return selectGeminiFlashLiteModels(models)[0] || null;
}

export function selectGeminiFlashLiteModels(models) {
  const stable = (Array.isArray(models) ? models : []).flatMap((entry) => {
    const name = typeof entry?.name === "string" ? entry.name.replace(/^models\//, "") : "";
    const methods = Array.isArray(entry?.supportedGenerationMethods) ? entry.supportedGenerationMethods : [];
    if (!/^gemini-[a-z0-9.-]*flash-lite(?:-[a-z0-9.-]+)?$/i.test(name) || !methods.includes("generateContent") ||
        /(?:^|[-.])(preview|experimental|exp|latest)(?:$|[-.])/i.test(name)) return [];
    return [name];
  });
  return [...new Set(stable)].sort((left, right) => {
    if (left === GEMINI_DEFAULT_MODEL) return -1;
    if (right === GEMINI_DEFAULT_MODEL) return 1;
    return left.localeCompare(right, "en");
  });
}

// 仅记录 Provider 回退类别与状态，绝不记录 Key、输入正文、URL 或供应商原始响应。
function logAnalysisProviderFallback(provider, reason, httpStatus) {
  const diagnostic = { event: "candidate_analysis_provider_fallback", provider, reason };
  if (Number.isInteger(httpStatus)) diagnostic.http_status = httpStatus;
  console.warn(JSON.stringify(diagnostic));
}

// 控制台只记录固定分类与可选 HTTP 状态，不包含密钥、正文、来源 URL 或错误响应。
function logAnalysisUnavailable(reason, httpStatus) {
  const diagnostic = { event: "candidate_analysis_unavailable", reason };
  if (Number.isInteger(httpStatus)) diagnostic.http_status = httpStatus;
  console.warn(JSON.stringify(diagnostic));
}

class AnalysisUnavailableError extends Error {
  constructor(reason, httpStatus) {
    super("analysis unavailable");
    this.name = "AnalysisUnavailableError";
    this.reason = reason;
    this.httpStatus = httpStatus;
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

// GLM-4.5-Flash 是首选免费分析器：只接收已受控抓取和裁剪的条目文本，密钥不会离开 Worker。
async function requestGlmAnalysis(env, page, input) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(GLM_CHAT_COMPLETIONS_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${env.ZAI_API_KEY}` },
      signal: controller.signal,
      body: JSON.stringify({
        model: GLM_DEFAULT_MODEL,
        stream: false,
        temperature: 0,
        max_tokens: 1800,
        thinking: { type: "disabled" },
        response_format: { type: "json_object" },
        messages: [
          { role: "system", content: "你是严谨的竞品研究助手。只根据输入页面作答，输出一个 JSON 对象，必须具有 feature_title、feature_summary、conclusion、facts、inference、competitive_impact、confidence、publication_time 字段。feature_title 是简洁的简体中文功能主题，feature_summary 是该具体功能的简洁简体中文摘要。不得猜测或伪造事实和发布时间；无法确认发布时间时 publication_time 使用 not_found 或 unverified，value 为 null。" },
          { role: "user", content: `来源标题：${page.title || "未提供"}\n来源 URL：${page.canonicalUrl}\n清洗后的页面正文：\n${input}` },
        ],
      }),
    });
    if (!response.ok) throw new AnalysisUnavailableError("glm_http_status", response.status);
    let payload;
    try { payload = await response.json(); } catch { throw new AnalysisUnavailableError("glm_malformed_response"); }
    const raw = payload?.choices?.[0]?.message?.content;
    if (typeof raw !== "string") throw new AnalysisUnavailableError("glm_malformed_response");
    try { return validateAnalysis(JSON.parse(raw), input); }
    catch { throw new AnalysisUnavailableError("glm_invalid_response"); }
  } finally {
    clearTimeout(timeout);
  }
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
          systemInstruction: { parts: [{ text: "你是严谨的竞品研究助手。只根据输入页面作答。feature_title 必须是简洁的简体中文功能主题，feature_summary 必须是该具体功能的简洁简体中文摘要；所有其他生成字段也必须使用简体中文。推断和竞争影响必须明确标注。不得补充、猜测或伪造事实和发布时间。无法确认发布时间时标为 not_found 或 unverified，value 必须为 null。" }] },
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
    if (!response.ok) throw new AnalysisUnavailableError("gemini_http_status", response.status);
    let payload;
    try {
      payload = await response.json();
    } catch {
      throw new AnalysisUnavailableError("malformed_response");
    }
    const raw = payload?.candidates?.[0]?.content?.parts?.[0]?.text;
    if (typeof raw !== "string") throw new AnalysisUnavailableError("malformed_response");
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch {
      throw new AnalysisUnavailableError("malformed_response");
    }
    try {
      return validateAnalysis(parsed, input);
    } catch {
      throw new AnalysisUnavailableError("invalid_response");
    }
  } finally {
    clearTimeout(timeout);
  }
}

function analysisJsonSchema() {
  return {
    type: "object",
    additionalProperties: false,
    required: ["feature_title", "feature_summary", "conclusion", "facts", "inference", "competitive_impact", "confidence", "publication_time"],
    properties: {
      feature_title: { type: "string", minLength: 2, maxLength: 24, description: "简洁的简体中文功能主题" },
      feature_summary: { type: "string", minLength: 6, maxLength: 160, description: "该具体功能的简洁简体中文摘要" },
      conclusion: { type: "string" },
      facts: { type: "array", minItems: 2, maxItems: 4, items: { type: "string" } },
      inference: { type: "object", additionalProperties: false, required: ["label", "text"], properties: { label: { type: "string", enum: ["推断"] }, text: { type: "string" } } },
      competitive_impact: { type: "object", additionalProperties: false, required: ["label", "text"], properties: { label: { type: "string", enum: ["竞争影响"] }, text: { type: "string" } } },
      confidence: { type: "string", enum: ["high", "medium", "low"] },
      publication_time: { type: "object", additionalProperties: false, required: ["status", "value", "source_text"], properties: { status: { type: "string", enum: ["verified", "not_found", "unverified"] }, value: { type: "string", nullable: true }, source_text: { type: "string", nullable: true } } },
    },
  };
}

// 输出二次校验：展示字段必须为简体中文；仅已验证发布时间需要回指输入原文。
export function validateAnalysis(value, input) {
  if (!value || typeof value !== "object" || !isSimplifiedChineseText(value.feature_title) ||
      Array.from(value.feature_title.trim()).length > 24 || !isSimplifiedChineseText(value.feature_summary) ||
      Array.from(value.feature_summary.trim()).length > 160 || typeof value.conclusion !== "string" || !value.conclusion.trim() ||
      !Array.isArray(value.facts) || value.facts.length < 2 || value.facts.length > 4 || !value.facts.every((fact) => typeof fact === "string" && fact.trim()) ||
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

function isSimplifiedChineseText(value) {
  return typeof value === "string" && value.trim().length > 0 &&
    SIMPLIFIED_CHINESE_TEXT_PATTERN.test(value) && !LATIN_TEXT_PATTERN.test(value);
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

async function deleteRecords(env, table, column, value) {
  return supabaseRequest(env, `/rest/v1/${table}?${column}=eq.${encodeURIComponent(value)}`, {
    method: "DELETE", headers: { Prefer: "return=minimal" },
  });
}

async function deleteStorageObject(env, objectPath, fetchImpl = fetch) {
  const response = await fetchImpl(storageObjectUrl(env, objectPath), {
    method: "DELETE",
    headers: { apikey: env.SUPABASE_SERVICE_ROLE_KEY, Authorization: `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}` },
  });
  if (!response.ok) throw new Error(`附件删除返回 HTTP ${response.status}。`);
}

// Storage 对象读取：路径逐段编码，服务角色只发送给 Supabase，并对响应 MIME 与实际字节数重新设限。
async function retrieveStorageObject(env, objectPath, fetchImpl = fetch) {
  const response = await fetchImpl(storageObjectUrl(env, objectPath), {
    headers: { apikey: env.SUPABASE_SERVICE_ROLE_KEY, Authorization: `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}` },
  });
  if (!response.ok) throw new Error(`附件存储返回 HTTP ${response.status}。`);
  const mediaType = (response.headers.get("Content-Type") || "").split(";", 1)[0].trim().toLowerCase();
  const declaredSize = Number(response.headers.get("Content-Length"));
  if (!ALLOWED_IMAGE_TYPES.has(mediaType) ||
      Number.isFinite(declaredSize) && declaredSize > MAX_IMAGE_BYTES) {
    throw new HttpError(415, "unsafe_attachment", "附件类型或大小不受支持。");
  }
  const bytes = new Uint8Array(await response.arrayBuffer());
  if (bytes.byteLength > MAX_IMAGE_BYTES) {
    throw new HttpError(415, "unsafe_attachment", "附件类型或大小不受支持。");
  }
  return { bytes, mediaType };
}

function storageObjectUrl(env, objectPath) {
  const encodedPath = String(objectPath || "").split("/").map(encodeURIComponent).join("/");
  return `${env.SUPABASE_URL}/storage/v1/object/${CANDIDATE_ATTACHMENTS_BUCKET}/${encodedPath}`;
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
    "Access-Control-Allow-Methods": "GET, POST, DELETE",
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
