import re
import unittest
from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "index.html").read_text(encoding="utf-8")


class SourceCaptureFrontendContractTests(unittest.TestCase):
    def test_runtime_config_accepts_only_the_fixed_same_origin_capture_proxy(self):
        self.assertIn("/api/source-capture", SOURCE)
        self.assertIn("parsedWorkerUrl.origin === window.location.origin", SOURCE)
        self.assertIn("parsedWorkerUrl.pathname === '/api/source-capture'", SOURCE)

    def function_body(self, name, next_name=None):
        match = re.search(rf"function {name}\([^\n]*\) \{{(?P<body>.*?)\n    \}}", SOURCE, re.S)
        self.assertIsNotNone(match, name)
        return match.group("body")

    def test_capture_window_validates_order_future_and_builds_iso_payload(self):
        self.assertIn('id="captureWindowStart" type="datetime-local"', SOURCE)
        self.assertIn('id="captureWindowEnd" type="datetime-local"', SOURCE)
        validation = self.function_body("validateCaptureWindow", "openCaptureWindow")
        self.assertIn("start >= end", validation)
        self.assertIn("end > now", validation)
        self.assertIn("start: start.toISOString()", validation)
        self.assertIn("end: end.toISOString()", validation)
        request = self.function_body("requestManualSourceCapture")
        self.assertIn("JSON.stringify({ sourceId, observationWindow })", request)

    def test_capture_defaults_to_last_fetch_or_thirty_days_and_waits_for_confirmation(self):
        opener = self.function_body("openCaptureWindow", "setCaptureButtonLoading")
        self.assertIn("source.lastFetchedAt", opener)
        self.assertIn("30 * 24 * 60 * 60 * 1000", opener)
        self.assertIn("captureWindowEnd.value = toDateTimeLocalValue(now)", opener)
        source_click = re.search(
            r"if \(captureButton\) \{(?P<body>.*?)\n\s*\}", SOURCE, re.S
        )
        self.assertIsNotNone(source_click)
        self.assertIn("openCaptureWindow", source_click.group("body"))
        self.assertNotIn("requestManualSourceCapture", source_click.group("body"))
        self.assertIn("setSourceCaptureLoading(sourceIdValue, true)", SOURCE)

    def test_capture_loading_is_rendered_from_source_id_state_and_cleared_before_failure_alert(self):
        self.assertIn("const capturingSourceIds = new Set();", SOURCE)
        self.assertIn("function setSourceCaptureLoading(sourceId, isLoading)", SOURCE)
        self.assertIn("capturingSourceIds.has(item.id)", SOURCE)
        self.assertIn("setSourceCaptureLoading(sourceIdValue, true);", SOURCE)
        self.assertIn("setSourceCaptureLoading(sourceIdValue, false);\n        window.alert(`抓取失败：${error.message}`);", SOURCE)
        self.assertIn("finally {\n        setSourceCaptureLoading(sourceIdValue, false);", SOURCE)

    def test_local_only_source_cannot_request_worker(self):
        opener = self.function_body("openCaptureWindow", "setCaptureButtonLoading")
        self.assertIn("!sourceCaptureState.cloudSynced || !cloudSyncState.accessToken", opener)
        self.assertIn("return;", opener)
        submit = re.search(
            r"captureWindowForm\.addEventListener\('submit', async event => \{(?P<body>.*?)\n\s*\}\);",
            SOURCE,
            re.S,
        )
        self.assertIsNotNone(submit)
        self.assertIn("!sourceCaptureState.cloudSynced || !cloudSyncState.accessToken", submit.group("body"))

    def test_capture_repairs_a_locally_saved_source_missing_from_cloud_before_worker_request(self):
        request = self.function_body("requestManualSourceCapture")
        self.assertIn("await ensureSourceAvailableForManualCapture(sourceId)", request)
        self.assertLess(
            request.find("await ensureSourceAvailableForManualCapture(sourceId)"),
            request.find("fetch(`${config.sourceCaptureWorkerUrl}/manual-capture`"),
        )
        self.assertIn("const sourceCaptureRepairPromises = new Map();", SOURCE)
        self.assertIn("async function ensureSourceAvailableForManualCapture(sourceId)", SOURCE)
        self.assertIn("await flushCloudOutbox()", SOURCE)
        self.assertIn("workspace_id=eq.${encodeURIComponent(workspaceId)}", SOURCE)
        self.assertIn("on_conflict=id", SOURCE)
        self.assertIn("resolution=merge-duplicates,return=representation", SOURCE)
        self.assertIn("existingMutation?.operation === 'create'", SOURCE)
        self.assertIn("filter(item => item !== existingMutation)", SOURCE)
        self.assertIn("sourceCaptureRepairPromises.delete(sourceId)", SOURCE)

    def test_candidate_card_only_renders_feature_summary_and_chinese_title(self):
        title = self.function_body("getCandidateFeatureTitle", "renderCandidateAnalysis")
        self.assertIn("'feature_title'", title)
        self.assertIn("'featureTitle'", title)
        self.assertIn("/[\\u3400-\\u9fff]/", title)
        self.assertIn("待审核功能更新", title)

        structured = self.function_body("renderCandidateAnalysis", "fetchCandidateAttachmentBlob")
        self.assertIn("功能总结", structured)
        self.assertIn("'feature_summary'", structured)
        self.assertIn("'featureSummary'", structured)
        self.assertIn("AI 分析暂不可用，暂无功能总结。", structured)
        self.assertNotIn("analysisStatus", structured)
        self.assertNotIn("rate_limited", structured)
        analysis = self.function_body("getCandidateAnalysis", "analysisText")
        self.assertIn("candidate?.title", analysis)
        for forbidden in ("quotedText", "candidate.summary", "facts", "inference", "competitive_impact", "quotes", "quotePairs", "原始摘录", "原文引句"):
            self.assertNotIn(forbidden, structured)

        queue = self.function_body("renderReviewQueue", "prepareCandidateAsEvidence")
        self.assertIn("getCandidateFeatureTitle(item)", queue)
        self.assertNotIn("item.title", queue)
        self.assertNotIn("quotedText", queue)
        for label in ("检测窗口", "发布时间", "发布状态"):
            self.assertIn(label, queue)

    def test_hard_delete_is_candidate_only_and_uses_worker(self):
        deletion = self.function_body("hardDeleteCloudCandidate")
        self.assertIn("sourceCaptureWorkerUrl", deletion)
        self.assertIn("hardDeleteCloudCaptureRun", SOURCE)
        self.assertIn("data-delete-capture-run-id", SOURCE)
        self.assertIn("删除此抓取批次", SOURCE)
        self.assertIn("删除 Candidate", SOURCE)
        self.assertIn("正式证据、矩阵和洞察不会被删除", SOURCE)
        self.assertIn("抓取批次删除后端尚未发布", SOURCE)
        self.assertIn("ensureFreshCloudAccessToken", deletion)
        self.assertNotIn("cloudRestRequest", deletion)
        self.assertNotIn("enqueueCloudMutation", deletion)
        for forbidden in ("source_capture_runs", "source_capture_snapshots", "evidence", "matrix", "insight"):
            self.assertNotIn(forbidden, deletion)
        self.assertIn("永久删除此 Candidate，且只删除此 Candidate", SOURCE)
        self.assertIn("sourceCaptureState.candidates = sourceCaptureState.candidates.filter", SOURCE)
        self.assertIn('data-delete-candidate-id=', SOURCE)


if __name__ == "__main__":
    unittest.main()
