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
SERVICE_ROLE_GRANTS_MIGRATION_PATH = (
    ROOT / "supabase" / "migrations" / "20260803010000_source_capture_worker_service_role_grants.sql"
)
PREVIEW_AI_MIGRATION_PATH = (
    ROOT / "supabase" / "migrations" / "20260803020000_preview_candidate_ai_analysis.sql"
)
SUBPAGE_MIGRATION_PATH = (
    ROOT / "supabase" / "migrations" / "20260803030000_changelog_subpage_candidates.sql"
)
ATTACHMENT_MIGRATION_PATH = (
    ROOT / "supabase" / "migrations" / "20260803040000_candidate_attachments.sql"
)
PRESENTATION_MIGRATION_PATH = (
    ROOT / "supabase" / "migrations" / "20260803050000_candidate_presentation_contract.sql"
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

    def test_worker_service_role_can_access_only_capture_pipeline_tables(self):
        migration = SERVICE_ROLE_GRANTS_MIGRATION_PATH.read_text(encoding="utf-8")
        self.assertIn("grant usage on schema public to service_role;", migration)
        for table in [
            "competitor_sources",
            "workspace_members",
            "source_capture_runs",
            "source_capture_snapshots",
            "source_capture_candidates",
        ]:
            self.assertRegex(migration, rf"grant select(?:, insert(?:, update)?)? on table public\.{table} to service_role;")
        self.assertNotIn("to anon", migration.lower())
        self.assertNotIn("to authenticated", migration.lower())

    def test_changelog_candidates_store_traceable_selected_entry_sets(self):
        migration = SUBPAGE_MIGRATION_PATH.read_text(encoding="utf-8")
        self.assertIn("alter table public.source_capture_candidates", migration)
        self.assertIn("selected_entries jsonb", migration)
        self.assertIn("excluded_missing_date_count integer", migration)
        self.assertNotRegex(migration, r"public\.(evidence|matrix_cells|insights)\b")

    def test_candidate_attachments_are_private_member_readable_and_worker_managed(self):
        migration = ATTACHMENT_MIGRATION_PATH.read_text(encoding="utf-8")
        self.assertIn("insert into storage.buckets", migration)
        self.assertIn("'candidate-attachments'", migration)
        self.assertIn("false", migration.lower())
        self.assertIn("create table public.candidate_attachments", migration)
        self.assertIn("references public.source_capture_candidates(id) on delete cascade", migration)
        self.assertIn("alter table public.candidate_attachments enable row level security", migration)
        self.assertRegex(migration, r"for select\s+to authenticated")
        self.assertIn("grant select on table public.candidate_attachments to authenticated;", migration)
        self.assertIn("grant delete on table public.source_capture_candidates to service_role;", migration)
        self.assertIn("public.is_workspace_member(workspace_id)", migration)
        self.assertIn("to service_role", migration)
        self.assertNotRegex(migration, r"for delete\s+to authenticated")
        self.assertNotIn("delete from storage.objects", migration.lower())

    def test_preview_analysis_is_candidate_only_and_has_structured_status_metadata(self):
        migration = PREVIEW_AI_MIGRATION_PATH.read_text(encoding="utf-8")
        self.assertIn("alter table public.source_capture_candidates", migration)
        for column in [
            "analysis_status", "analysis jsonb", "analysis_model",
            "analysis_schema_version", "publication_time_status",
            "detection_window_start", "detection_window_end",
        ]:
            self.assertIn(column, migration)
        self.assertNotRegex(migration, r"alter table public\.(evidence|matrix_cells|insights)\b")
        self.assertNotRegex(migration, r"insert into public\.(evidence|matrix_cells|insights)\b")

    def test_candidate_presentation_contract_allows_null_quotes_and_versions_analysis(self):
        migration = PRESENTATION_MIGRATION_PATH.read_text(encoding="utf-8")
        self.assertIn("alter table public.source_capture_candidates", migration)
        self.assertIn("alter column quoted_text drop not null", migration)
        self.assertIn("alter column quoted_text drop default", migration)
        self.assertIn("preview_candidate_analysis_v2", migration)
        self.assertNotRegex(migration, r"public\.(evidence|matrix_cells|insights)\b")

    def test_daily_ai_budget_reservation_is_atomic_fail_closed_and_service_role_only(self):
        migration = PREVIEW_AI_MIGRATION_PATH.read_text(encoding="utf-8")
        self.assertIn("create table public.source_capture_ai_daily_usage", migration)
        self.assertIn("create function public.reserve_source_capture_ai_budget", migration)
        self.assertIn("on conflict (usage_date) do update", migration)
        self.assertIn("requested_tokens > daily_token_limit", migration)
        self.assertIn("usage.reserved_requests < daily_request_limit", migration)
        self.assertIn("usage.reserved_tokens + excluded.reserved_tokens <= daily_token_limit", migration)
        self.assertIn("revoke all on function public.reserve_source_capture_ai_budget", migration)
        self.assertIn("grant execute on function public.reserve_source_capture_ai_budget(integer, integer, bigint) to service_role", migration)
        self.assertNotIn("to anon", migration.lower())
        self.assertNotIn("to authenticated", migration.lower())


if __name__ == "__main__":
    unittest.main()
