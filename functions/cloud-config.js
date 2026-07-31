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

  if (!isHttpsUrl(url) || !publishableKey) {
    return new Response("", { headers: RESPONSE_HEADERS });
  }

  const config = safeJson({ url, publishableKey });
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

function safeJson(value) {
  return JSON.stringify(value).replace(/[<>&\u2028\u2029]/g, (character) => {
    return `\\u${character.charCodeAt(0).toString(16).padStart(4, "0")}`;
  });
}
