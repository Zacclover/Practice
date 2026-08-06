const RESPONSE_HEADERS = {
  "Cache-Control": "no-store",
  "Content-Type": "application/javascript; charset=utf-8",
};

// 云端运行时配置：仅在环境变量有效时向浏览器发布公开的 Supabase 配置。
export function onRequest({ env }) {
  const url = typeof env?.SUPABASE_URL === "string" ? env.SUPABASE_URL.trim() : "";
  const publishableKey = typeof env?.SUPABASE_PUBLISHABLE_KEY === "string"
    ? env.SUPABASE_PUBLISHABLE_KEY.trim()
    : "";

  // 来源抓取仅向浏览器发布同源代理路径，外部 Worker 地址不会离开服务端。
  const sourceCaptureWorkerUrl = isValidSourceCaptureUpstream(env?.SOURCE_CAPTURE_WORKER_URL)
    ? "/api/source-capture"
    : "";

  if (!isHttpsUrl(url) || !publishableKey) {
    return new Response("", { headers: RESPONSE_HEADERS });
  }

  const config = safeJson({
    SUPABASE_URL: url,
    SUPABASE_PUBLISHABLE_KEY: publishableKey,
    ...(sourceCaptureWorkerUrl ? { SOURCE_CAPTURE_WORKER_URL: sourceCaptureWorkerUrl } : {}),
  });
  return new Response(
    `window.COMPETITOR_INSIGHTS_CLOUD_CONFIG = ${config};`,
    { headers: RESPONSE_HEADERS },
  );
}

function isHttpsUrl(value) {
  try {
    return new URL(value).protocol === "https:";
  } catch {
    return false;
  }
}

function isValidSourceCaptureUpstream(value) {
  if (typeof value !== "string" || !value.trim()) return "";
  try {
    const parsed = new URL(value.trim());
    if (parsed.protocol !== "https:" || parsed.username || parsed.password || parsed.search || parsed.hash) return "";
    return true;
  } catch {
    return "";
  }
}

function safeJson(value) {
  return JSON.stringify(value).replace(/[<>&\u2028\u2029]/g, (character) => {
    return `\\u${character.charCodeAt(0).toString(16).padStart(4, "0")}`;
  });
}
