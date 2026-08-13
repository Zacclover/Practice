const JSON_HEADERS = {
  "Cache-Control": "no-store",
  "Content-Type": "application/json; charset=utf-8",
};

const UUID_PATTERN = "[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}";
const ROUTES = [
  { pattern: new RegExp(`^/manual-capture$`), methods: new Set(["POST", "OPTIONS"]) },
  { pattern: new RegExp(`^/capture-runs/${UUID_PATTERN}$`, "i"), methods: new Set(["DELETE", "OPTIONS"]) },
  { pattern: new RegExp(`^/candidate-attachments/${UUID_PATTERN}$`, "i"), methods: new Set(["GET", "OPTIONS", "DELETE"]) },
  { pattern: new RegExp(`^/candidate-attachments/${UUID_PATTERN}/${UUID_PATTERN}$`, "i"), methods: new Set(["GET", "OPTIONS"]) },
];

// 同源 Pages 代理：浏览器只访问固定的来源抓取路由，绝不接收任意目标地址。
export async function onRequest(context) {
  return forwardSourceCaptureRequest(context, context.params?.path);
}

// 精确路由与多段路由共用同一白名单转发器，避免浏览器直连 workers.dev。
export async function forwardSourceCaptureRequest({ env, request }, routeSegments) {
  const path = normalizePath(routeSegments);
  const route = ROUTES.find(({ pattern }) => pattern.test(path));
  if (!route) return safeJsonResponse("not_found", 404);

  const method = request.method.toUpperCase();
  if (!route.methods.has(method)) {
    return safeJsonResponse("method_not_allowed", 405, {
      Allow: [...route.methods].join(", "),
    });
  }

  const upstream = parseUpstream(env?.SOURCE_CAPTURE_WORKER_URL);
  if (!upstream) return safeJsonResponse("service_unavailable", 503);

  const headers = forwardHeaders(request.headers);
  const init = { method, headers, redirect: "manual" };
  if (method === "POST") init.body = request.body;

  try {
    return await fetch(new URL(joinPath(upstream.pathname, path), upstream.origin), init);
  } catch {
    return safeJsonResponse("upstream_unavailable", 502);
  }
}

function normalizePath(value) {
  const segments = Array.isArray(value) ? value : String(value || "").split("/");
  return `/${segments.filter(Boolean).join("/")}`;
}

function parseUpstream(value) {
  if (typeof value !== "string" || !value.trim()) return null;
  try {
    const upstream = new URL(value.trim());
    if (
      upstream.protocol !== "https:"
      || !upstream.hostname
      || upstream.username
      || upstream.password
      || upstream.search
      || upstream.hash
    ) return null;
    return upstream;
  } catch {
    return null;
  }
}

function joinPath(basePath, path) {
  return `${basePath.replace(/\/$/, "")}${path}`;
}

function forwardHeaders(source) {
  const headers = new Headers();
  for (const name of ["Authorization", "Content-Type", "Origin"]) {
    const value = source.get(name);
    if (value) headers.set(name, value);
  }
  return headers;
}

function safeJsonResponse(error, status, extraHeaders = {}) {
  return new Response(JSON.stringify({ error }), {
    status,
    headers: { ...JSON_HEADERS, ...extraHeaders },
  });
}
