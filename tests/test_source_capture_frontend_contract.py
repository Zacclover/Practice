import re
import unittest
from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "index.html").read_text(encoding="utf-8")


class SourceCaptureFrontendContractTests(unittest.TestCase):
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
        self.assertIn("setCaptureButtonLoading(captureButton, true)", SOURCE)

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

    def test_structured_candidate_and_concise_fallback_are_rendered(self):
        structured = self.function_body("renderCandidateAnalysis", "renderReviewQueue")
        for label in ("中文结论", "事实", "推断", "竞争影响", "置信度", "原文引句与中文释义", "中文释义"):
            self.assertIn(label, structured)
        self.assertIn(".slice(0, 3)", structured)
        self.assertIn(".slice(0, 360)", structured)
        self.assertIn("candidate.quotedText || candidate.summary", structured)
        queue = self.function_body("renderReviewQueue", "prepareCandidateAsEvidence")
        for label in ("检测窗口", "发布时间", "发布状态"):
            self.assertIn(label, queue)

    def test_hard_delete_is_candidate_only_and_uses_outbox_baseline(self):
        deletion = self.function_body("hardDeleteCloudCandidate")
        self.assertIn("source_capture_candidates", deletion)
        self.assertIn("enqueueCloudMutation", deletion)
        self.assertIn("'delete'", deletion)
        for forbidden in ("source_capture_runs", "source_capture_snapshots", "evidence", "matrix", "insight"):
            self.assertNotIn(forbidden, deletion)
        self.assertIn("永久删除此 Candidate，且只删除此 Candidate", SOURCE)
        self.assertIn("sourceCaptureState.candidates = sourceCaptureState.candidates.filter", SOURCE)
        self.assertIn('data-delete-candidate-id=', SOURCE)


if __name__ == "__main__":
    unittest.main()
