import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260802020000_source_capture_authenticated_grants.sql"
TABLES = (
    "competitor_sources",
    "source_capture_runs",
    "source_capture_snapshots",
    "source_capture_candidates",
)


class SourceCaptureAuthenticatedGrantTests(unittest.TestCase):
    def test_authenticated_members_receive_table_privileges_before_rls_filters_rows(self):
        source = MIGRATION.read_text(encoding="utf-8")
        for table in TABLES:
            self.assertRegex(
                source,
                rf"grant select, insert, update, delete on table public\.{table} to authenticated;",
            )


if __name__ == "__main__":
    unittest.main()
