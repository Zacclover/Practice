import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT / "supabase" / "migrations" / "20260731010000_source_capture_review_queue.sql"
)
MANUAL_MIGRATION_PATH = (
    ROOT / "supabase" / "migrations" / "20260803000000_manual_source_capture.sql"
)


class SourceCaptureSchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MIGRATION_PATH.read_text(encoding="utf-8")

    def test_capture_pipeline_keeps_sources_runs_and_review_candidates_separate_from_evidence(self):
        for table in [
            "competitor_sources",
            "source_capture_runs",
            "source_capture_snapshots",
            "source_capture_candidates",
        ]:
            self.assertRegex(
                self.source,
                rf"create table public\.{table}\s*\(",
                f"缺少 public.{table}。",
            )

        self.assertIn("competitor_id uuid not null", self.source)
        self.assertIn("source_url text not null", self.source)
        self.assertIn("content_hash text not null", self.source)
        self.assertIn("status text not null default 'pending'", self.source)
        self.assertIn("unique (source_id, content_hash)", self.source)
        self.assertNotIn("insert into public.evidence", self.source.lower())

    def test_only_public_http_sources_and_explicit_review_statuses_are_allowed(self):
        self.assertIn("check (url ~ '^https://')", self.source)
        self.assertIn("check (source_type in", self.source)
        self.assertIn("check (status in ('queued', 'running', 'completed', 'failed'))", self.source)
        self.assertIn("check (status in ('pending', 'approved', 'rejected'))", self.source)

    def test_capture_records_are_workspace_member_scoped_with_rls(self):
        for table in [
            "competitor_sources",
            "source_capture_runs",
            "source_capture_snapshots",
            "source_capture_candidates",
        ]:
            self.assertIn(
                f"alter table public.{table} enable row level security;",
                self.source,
            )
            self.assertRegex(
                self.source,
                rf'create policy "workspace members manage {table}"\s+on public\.{table}',
            )

    def test_manual_capture_runs_are_queryable_per_source_and_created_at(self):
        migration = MANUAL_MIGRATION_PATH.read_text(encoding="utf-8")
        self.assertIn("add column source_id uuid", migration)
        self.assertIn("foreign key (workspace_id, tab_id, source_id)", migration)
        self.assertRegex(
            migration,
            r"source_capture_runs_manual_cooldown_idx[\s\S]*source_id, trigger_type, created_at desc",
        )
        self.assertNotIn("last_fetched_at", migration)


if __name__ == "__main__":
    unittest.main()
