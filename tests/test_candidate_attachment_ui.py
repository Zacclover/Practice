import re
import unittest
from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "index.html").read_text(encoding="utf-8")


class CandidateAttachmentUiContractTests(unittest.TestCase):
    def function_body(self, name):
        match = re.search(rf"(?:async )?function {name}\([^\n]*\) \{{(?P<body>.*?)\n    \}}", SOURCE, re.S)
        self.assertIsNotNone(match, name)
        return match.group("body")

    def test_metadata_is_hydrated_and_mapped_to_its_candidate(self):
        self.assertIn("[...cloudSnapshotTables, 'candidate_attachments']", SOURCE)
        mapping = self.function_body("mapCloudSnapshotToV3")
        self.assertIn("attachment.candidate_id === item.id", mapping)
        self.assertIn("attachments:", mapping)
        self.assertIn("sourceUrl: item.source_url", mapping)
        self.assertIn("title: item.title, summary: item.summary", mapping)

    def test_private_images_use_worker_bearer_get_and_blob_urls_only(self):
        request = self.function_body("fetchCandidateAttachmentBlob")
        self.assertIn("sourceCaptureWorkerUrl", request)
        self.assertIn("/candidate-attachments/", request)
        self.assertIn("Authorization", request)
        self.assertIn("Bearer ${cloudSyncState.accessToken}", request)
        self.assertIn("return response.blob()", request)
        strip = self.function_body("renderCandidateAttachmentStrip")
        self.assertNotIn("attachment.url", strip)
        self.assertNotIn("http://", strip)
        self.assertNotIn("https://", strip)
        self.assertNotIn("candidate.title", strip)
        self.assertIn("getCandidateFeatureTitle(candidate)", strip)
        self.assertIn("attachments.slice(0, 3)", strip)

    def test_object_urls_are_revoked_for_thumbnails_and_full_image(self):
        thumbnails = self.function_body("revokeCandidateAttachmentThumbnails")
        close = self.function_body("closeCandidateAttachmentDialog")
        self.assertIn("URL.revokeObjectURL", thumbnails)
        self.assertIn("URL.revokeObjectURL", close)
        self.assertIn("reviewQueueDialog.addEventListener('close', revokeCandidateAttachmentThumbnails)", SOURCE)

    def test_dialog_is_accessible_and_escape_closes_it(self):
        self.assertRegex(SOURCE, r'<dialog id="candidateAttachmentDialog"[^>]+aria-labelledby="candidateAttachmentDialogTitle"')
        self.assertIn('id="candidateAttachmentDialogTitle"', SOURCE)
        self.assertIn('id="closeCandidateAttachmentButton"', SOURCE)
        self.assertIn("candidateAttachmentDialog.addEventListener('cancel'", SOURCE)
        self.assertIn("closeCandidateAttachmentButton.focus()", SOURCE)

    def test_cloud_delete_is_worker_only_and_waited_before_local_removal(self):
        deletion = self.function_body("hardDeleteCloudCandidate")
        self.assertIn("method: 'DELETE'", deletion)
        self.assertNotIn("cloudRestRequest", deletion)
        self.assertNotIn("enqueueCloudMutation", deletion)
        handler = re.search(r"reviewQueueList\.addEventListener\('click', async event => \{(?P<body>.*?)\n    \}\);", SOURCE, re.S)
        self.assertIsNotNone(handler)
        body = handler.group("body")
        self.assertLess(body.index("await hardDeleteCloudCandidate(candidateId)"), body.index("sourceCaptureState.candidates = sourceCaptureState.candidates.filter"))
        for forbidden in ("evidenceItems", "comparisonData", "insights", "source_capture_runs", "source_capture_snapshots"):
            self.assertNotIn(forbidden, deletion)

    def test_local_candidates_have_no_attachment_ui(self):
        strip = self.function_body("renderCandidateAttachmentStrip")
        self.assertIn("!sourceCaptureState.cloudSynced", strip)
        request = self.function_body("fetchCandidateAttachmentBlob")
        self.assertIn("!cloudSyncState.accessToken", request)
        self.assertIn("!config.sourceCaptureWorkerUrl", request)


if __name__ == "__main__":
    unittest.main()
