import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
WORKER = (ROOT / "workers" / "source-capture.mjs").read_text(encoding="utf-8")
MIGRATIONS = "\n".join(
    path.read_text(encoding="utf-8")
    for path in sorted((ROOT / "supabase" / "migrations").glob("*.sql"))
)


class LocalAiEvidenceFlowTests(unittest.TestCase):
    def test_capture_saves_raw_snapshot_without_creating_candidate(self):
        self.assertIn("capture_mode: triggerType", WORKER)
        self.assertIn('summary_status: "pending"', WORKER)
        self.assertIn("Candidate 必须由浏览器本地 AI 总结成功后创建", WORKER)
        self.assertIn("collectDatedUpdateSections", WORKER)
        self.assertNotIn('insertRecord(env, "source_capture_candidates"', WORKER)

    def test_public_html_images_are_normalized_as_snapshot_metadata(self):
        self.assertIn("export function extractPublicImageUrls", WORKER)
        self.assertIn("section.images", WORKER)
        self.assertIn("source_capture_snapshot_images", WORKER)
        self.assertIn("isSafePublicSourceUrl", WORKER)

    def test_review_queue_uses_one_competitor_batch_record_per_capture_source(self):
        self.assertIn("<h3>${escapeHtml(competitor?.name || '已移除竞品')}</h3>", INDEX)
        self.assertIn("来源：${escapeHtml(source?.label || '已移除来源')}", INDEX)
        self.assertIn("data-generate-summary-source-id", INDEX)
        self.assertIn("batchRawItems", INDEX)
        self.assertNotIn("rawItems.map(raw => `<article class=\"review-raw-item\"", INDEX)

    def test_batch_generation_has_visible_processing_states_and_preserves_local_only_boundary(self):
        self.assertIn("检查本机 WebGPU…", INDEX)
        self.assertIn("正在加载本地模型…", INDEX)
        self.assertIn("正在生成中文总结（${index + 1}/${rawItems.length}）", INDEX)
        self.assertIn("正在保存待审核证据（${index + 1}/${rawItems.length}）", INDEX)
        self.assertIn("const prefix = cacheHit ? '正在从本机模型缓存加载' : '正在下载本地模型';", INDEX)
        self.assertIn("getLocalModelButtonLabel", INDEX)
        self.assertIn("正在下载本地模型…", INDEX)
        self.assertIn("text-align: right", INDEX)
        self.assertIn("onProgress(progress)", INDEX)
        self.assertNotIn("lastPhase = progress.phase", INDEX)
        self.assertIn("downloadProgress", INDEX)
        self.assertIn("下载进度超过 5 分钟没有增加", INDEX)
        self.assertIn("已用 ${elapsedSec}s", INDEX)
        self.assertIn("local-summary-loader", INDEX)
        self.assertIn("stroke-dasharray=\"25 10\"", INDEX)
        self.assertIn("transform-box: fill-box", INDEX)
        self.assertNotIn("border-right-color: transparent", INDEX)
        self.assertIn("data-generate-summary-source-id", INDEX)

    def test_review_queue_shows_batch_count_and_local_summary_entry(self):
        self.assertIn("待总结证据（${batchRawItems.length}）", INDEX)
        self.assertIn("AI 总结生成证据", INDEX)
        self.assertIn("createCandidatesFromLocalSummary", INDEX)

    def test_local_model_input_is_token_budgeted_and_errors_are_localized(self):
        self.assertIn("truncateLocalEvidenceText", INDEX)
        self.assertIn("maxBudget = 1400", INDEX)
        self.assertIn("repair: true", INDEX)
        self.assertIn("isValidLocalChineseSummary", INDEX)
        self.assertIn("renderReviewQueue();", INDEX)
        self.assertIn("generate: prompt length", INDEX)
        self.assertIn("原始页面内容过长", INDEX)
        self.assertIn("LOCAL_MODEL_CACHE_NAME", INDEX)
        self.assertIn("fetchWithPersistentCache", INDEX)
        self.assertIn("caches.open(LOCAL_MODEL_CACHE_NAME)", INDEX)
        self.assertIn("navigator.storage?.persist", INDEX)
        self.assertIn("weightCacheHit", INDEX)
        self.assertIn("正在从本机模型缓存加载", INDEX)
        self.assertIn("downloadProgress: progressed && !fromCache", INDEX)
        self.assertIn("fetchArrayBuffer: async url", INDEX)
        self.assertIn("fetchJson: async url", INDEX)
        self.assertIn("本地模型输出未完成", INDEX)
        self.assertIn("maxLength: 400", INDEX)
        self.assertIn("maxTokens: 512", INDEX)

    def test_expired_cloud_session_refreshes_before_capture_or_rpc(self):
        self.assertIn("cloudAuthRefreshTokenKey", INDEX)
        self.assertIn("refreshCloudAccessToken", INDEX)
        self.assertIn("grant_type=refresh_token", INDEX)
        self.assertIn("ensureFreshCloudAccessToken", INDEX)
        self.assertIn("const accessToken = await ensureFreshCloudAccessToken();", INDEX)
        self.assertIn("response.status === 401 || response.status === 403", INDEX)

    def test_browser_local_inference_has_no_remote_fallback(self):
        readiness = re.search(
            r"async function checkLocalEvidenceModelReadiness\([^)]*\) \{(?P<body>.*?)\n    \}",
            INDEX,
            re.S,
        )
        self.assertIsNotNone(readiness)
        self.assertIn("navigator.gpu", readiness.group("body"))
        self.assertIn("requestAdapter", readiness.group("body"))
        inference = re.search(
            r"async function generateLocalEvidenceSummary\([^)]*\) \{(?P<body>.*?)\n    \}",
            INDEX,
            re.S,
        )
        self.assertIsNotNone(inference)
        self.assertIn("BitGPU", INDEX)
        self.assertIn("localEvidenceModelConfig", INDEX)
        self.assertIn("await model.generate", inference.group("body"))
        self.assertNotIn("fetch(", inference.group("body"))
        self.assertNotIn("cloudRestRequest", inference.group("body"))

    def test_schema_removes_cloud_ai_budget_and_links_candidate_images(self):
        self.assertIn("drop function if exists public.reserve_source_capture_ai_budget", MIGRATIONS)
        self.assertIn("drop table if exists public.source_capture_ai_daily_usage", MIGRATIONS)
        self.assertIn("create table public.source_capture_snapshot_images", MIGRATIONS)
        self.assertIn("alter table public.candidate_attachments", MIGRATIONS)
        self.assertIn("source_url, image_url", MIGRATIONS)
        self.assertIn("create function public.create_local_summary_candidate", MIGRATIONS)
        self.assertIn("status text not null default 'pending'", MIGRATIONS)
        self.assertIn("revoke insert, update, delete on table public.source_capture_candidates from authenticated", MIGRATIONS)
        self.assertIn("workspace members read source_capture_candidates", MIGRATIONS)
        self.assertIn("for update", MIGRATIONS)
        self.assertIn("snapshot_already_summarized", MIGRATIONS)
        self.assertIn("summary_status = 'generated'", MIGRATIONS)

    def test_placeholder_summary_values_are_rejected(self):
        self.assertNotIn('输出示例：{"featureTitle":"中文功能主题"', INDEX)
        self.assertNotIn('严格输出：{"featureTitle":"中文功能主题"', INDEX)
        self.assertIn("isPlaceholderLocalChineseSummary", INDEX)
        self.assertIn("getLocalChineseSummaryValidationError", INDEX)
        self.assertIn("repairReason", INDEX)
        self.assertIn("repairField", INDEX)
        self.assertNotIn("pattern: '^[^A-Za-z]*", INDEX)
        self.assertIn("/[A-Za-z]/.test(summary)", INDEX)
        self.assertIn("localOutputs", INDEX)
        self.assertIn("本机输出诊断", INDEX)
        self.assertIn("role: 'system'", INDEX)
        self.assertIn("即使输入是英文，也只能输出简体中文", INDEX)
        self.assertIn("previousTitle", INDEX)
        self.assertIn("thinkBudget: 128", INDEX)
        self.assertIn("temperature: 0.5", INDEX)

    def test_unavailable_model_guidance_does_not_create_candidate(self):
        self.assertIn("请重新加载后重试", INDEX)
        self.assertIn("支持 WebGPU 的设备和浏览器", INDEX)
        handler = re.search(
            r"async function createCandidatesFromLocalSummary\([^)]*\) \{(?P<body>.*?)\n    \}",
            INDEX,
            re.S,
        )
        self.assertIsNotNone(handler)
        self.assertIn("checkLocalEvidenceModelReadiness", handler.group("body"))
        self.assertLess(
            handler.group("body").index("checkLocalEvidenceModelReadiness"),
            handler.group("body").index("create_local_summary_candidate"),
        )


if __name__ == "__main__":
    unittest.main()
