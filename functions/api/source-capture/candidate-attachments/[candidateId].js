import { forwardSourceCaptureRequest } from "../[[path]].js";

// Candidate 删除与附件路径由固定动态段传递，底层仍按 UUID 与 HTTP 方法白名单校验。
export function onRequest(context) {
  return forwardSourceCaptureRequest(context, ["candidate-attachments", context.params.candidateId]);
}
