import { forwardSourceCaptureRequest } from "../../[[path]].js";

// 私有附件读取使用两个固定动态段，底层仅允许候选与附件 UUID 的 GET 请求。
export function onRequest(context) {
  return forwardSourceCaptureRequest(context, [
    "candidate-attachments",
    context.params.candidateId,
    context.params.attachmentId,
  ]);
}
