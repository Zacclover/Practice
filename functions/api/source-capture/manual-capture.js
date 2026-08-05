import { forwardSourceCaptureRequest } from "./[[path]].js";

// 精确手动抓取入口：同源请求仍会经过受控 Worker 的 Bearer 与来源归属校验。
export function onRequest(context) {
  return forwardSourceCaptureRequest(context, ["manual-capture"]);
}
