import re
import unittest
from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "index.html").read_text(encoding="utf-8")


class CloudWorkspaceSyncRuntimeTests(unittest.TestCase):
    def test_account_area_owns_the_global_workspace_sync_states(self):
        self.assertIn('id="cloudWorkspaceSyncStatus"', SOURCE)
        self.assertIn('.cloud-account-panel .cloud-workspace-sync-status', SOURCE)
        self.assertIn('display: block !important;', SOURCE)
        self.assertIn('visibility: visible !important;', SOURCE)
        for state in ("syncing", "synchronized", "requires-import", "conflict", "failure"):
            self.assertIn(f"'{state}':", SOURCE)
        self.assertIn("updateCloudWorkspaceSyncStatus('failure'", SOURCE)

    def test_bootstrap_must_finish_before_workspace_can_report_synchronized(self):
        sync = re.search(
            r"async function synchronizeCloudWorkspace\(profile, accessToken\) \{(?P<body>.*?)\n    \}",
            SOURCE,
            re.S,
        )
        self.assertIsNotNone(sync)
        body = sync.group("body")
        self.assertLess(body.find("resolveCloudWorkspace"), body.find("updateCloudWorkspaceSyncStatus('synchronized'"))
        self.assertNotIn("updateCloudWorkspaceSyncStatus('synchronized'", body[:body.find("resolveCloudWorkspace")])

    def test_first_login_automatically_imports_local_workspace_without_prompt_or_backup(self):
        sync = re.search(
            r"async function synchronizeCloudWorkspace\(profile, accessToken\) \{(?P<body>.*?)\n    \}",
            SOURCE,
            re.S,
        )
        self.assertIsNotNone(sync)
        body = sync.group("body") if sync else ""
        self.assertIn("await importInitialLocalWorkspace()", body)
        self.assertNotIn("cloudImportDialog.showModal()", body)
        self.assertNotIn('id="cloudImportDialog"', SOURCE)
        importer = re.search(
            r"async function importInitialLocalWorkspace\(\) \{(?P<body>.*?)\n    \}",
            SOURCE,
            re.S,
        )
        self.assertIsNotNone(importer)
        self.assertNotIn("downloadWorkspaceBackup", importer.group("body") if importer else "")
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
