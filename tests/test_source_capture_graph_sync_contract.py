import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "index.html").read_text(encoding="utf-8")
MIGRATION = ROOT / "supabase" / "migrations" / "20260823010000_capture_source_graph_sync.sql"


class SourceCaptureGraphSyncContractTests(unittest.TestCase):
    def test_capture_sync_uses_one_authenticated_graph_rpc_before_worker_request(self):
        self.assertTrue(MIGRATION.exists(), "capture graph sync migration is required")
        migration = MIGRATION.read_text(encoding="utf-8")
        self.assertIn("upsert_capture_source_graph", migration)
        self.assertIn("security definer", migration)
        self.assertIn("is_workspace_member(target_workspace_id)", migration)
        self.assertIn("insert into public.workspace_tabs", migration)
        self.assertIn("insert into public.competitors", migration)
        self.assertIn("insert into public.competitor_sources", migration)
        self.assertLess(migration.find("insert into public.workspace_tabs"), migration.find("insert into public.competitors"))
        self.assertLess(migration.find("insert into public.competitors"), migration.find("insert into public.competitor_sources"))

        request = SOURCE[SOURCE.find("async function requestManualSourceCapture"):]
        self.assertIn("await ensureCaptureSourceGraph(sourceId)", request)
        self.assertLess(request.find("await ensureCaptureSourceGraph(sourceId)"), request.find("/manual-capture"))
        self.assertNotIn("ensureSourceAvailableForManualCapture", request)

    def test_every_source_create_and_update_uses_the_shared_graph_sync_path(self):
        self.assertIn("async function ensureCaptureSourceGraph(sourceId)", SOURCE)
        self.assertIn("rpc/upsert_capture_source_graph", SOURCE)
        self.assertIn("serializeCaptureSourceGraph(localSource, workspaceId)", SOURCE)
        self.assertIn("await ensureCaptureSourceGraph(record.id)", SOURCE)
        self.assertNotIn("competitor_sources?on_conflict=id", SOURCE)


if __name__ == "__main__":
    unittest.main()
