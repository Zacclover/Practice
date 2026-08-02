import re
import unittest
from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "index.html").read_text(encoding="utf-8")


class CloudWorkspaceSyncRuntimeTests(unittest.TestCase):
    def test_first_login_import_requires_confirmation_and_downloads_backup(self):
        self.assertIn('id="cloudImportDialog"', SOURCE)
        self.assertIn('id="confirmCloudImportButton"', SOURCE)
        self.assertIn("downloadWorkspaceBackup", SOURCE)
        self.assertIn("import_initial_workspace_snapshot", SOURCE)
        self.assertNotIn("void synchronizeCloudSourceCapture(profile, accessToken)", SOURCE)

    def test_cloud_snapshot_hydrates_all_v3_entities_and_source_review_data(self):
        function = re.search(
            r"function mapCloudSnapshotToV3\(snapshot\) \{(?P<body>.*?)\n    \}",
            SOURCE,
            re.S,
        )
        self.assertIsNotNone(function)
        body = function.group("body")
        for marker in (
            "workspace_tabs", "competitors", "dimensions", "evidence",
            "evidence_dimensions", "insights", "insight_competitors",
            "insight_dimensions", "insight_evidence", "matrix_cells",
            "competitor_sources", "source_capture_candidates",
        ):
            self.assertIn(marker, body)

    def test_entity_outbox_conditional_writes_conflicts_and_safe_pulls_are_wired(self):
        for marker in (
            "cloudOutboxStorageKey", "cloudConflictStorageKey",
            "enqueueCloudMutation", "flushCloudOutbox", "baselineUpdatedAt",
            "updated_at=eq.", "renderCloudConflicts", "visibilitychange",
            "window.addEventListener('focus'", "setInterval",
        ):
            self.assertIn(marker, SOURCE)
        self.assertIn('id="cloudConflictPanel"', SOURCE)
        flush = re.search(
            r"async function flushCloudOutbox\(\) \{(?P<body>.*?)\n    \}",
            SOURCE,
            re.S,
        )
        self.assertIsNotNone(flush)
        self.assertIn(
            "setCloudBaseline(await fetchCloudSnapshot",
            flush.group("body") if flush else "",
        )

    def test_candidates_remain_read_only_until_explicit_approval(self):
        self.assertIn("source_capture_candidates", SOURCE)
        self.assertIn("approveCloudCandidate", SOURCE)
        approval = re.search(
            r"async function approveCloudCandidate\(.*?\) \{(?P<body>.*?)\n    \}",
            SOURCE,
            re.S,
        )
        self.assertIsNotNone(approval)
        self.assertIn("approve_source_capture_candidate", approval.group("body"))


if __name__ == "__main__":
    unittest.main()
