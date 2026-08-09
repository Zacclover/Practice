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
        self.assertNotIn('insertRecord(env, "source_capture_candidates"', WORKER)

    def test_public_html_images_are_normalized_as_snapshot_metadata(self):
        self.assertIn("export function extractPublicImageUrls", WORKER)
        self.assertIn("page.imageUrls", WORKER)
        self.assertIn("source_capture_snapshot_images", WORKER)
        self.assertIn("isSafePublicSourceUrl", WORKER)

    def test_review_queue_groups_sources_and_exposes_local_summary_action(self):
        self.assertIn("待总结证据（${rawItems.length}）", INDEX)
        self.assertIn("来源竞品：${escapeHtml(competitor?.name", INDEX)
        self.assertIn("AI 总结生成证据", INDEX)
        self.assertIn("data-generate-summary-snapshot-id", INDEX)

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
        self.assertIn("create table public.candidate_attachments", MIGRATIONS)
        self.assertIn("create function public.create_local_summary_candidate", MIGRATIONS)
        self.assertIn("status text not null default 'pending'", MIGRATIONS)
        self.assertIn("revoke insert, update, delete on table public.source_capture_candidates from authenticated", MIGRATIONS)
        self.assertIn("workspace members read source_capture_candidates", MIGRATIONS)
        self.assertIn("for update", MIGRATIONS)
        self.assertIn("snapshot_already_summarized", MIGRATIONS)
        self.assertIn("summary_status = 'generated'", MIGRATIONS)

    def test_unavailable_model_guidance_does_not_create_candidate(self):
        self.assertIn("请重新加载后重试", INDEX)
        self.assertIn("支持 WebGPU 的设备和浏览器", INDEX)
        handler = re.search(
            r"async function createCandidateFromLocalSummary\([^)]*\) \{(?P<body>.*?)\n    \}",
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
