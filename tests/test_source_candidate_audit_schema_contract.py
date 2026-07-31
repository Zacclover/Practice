import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT / "supabase" / "migrations" / "20260731010000_source_candidate_audit.sql"
)


class SourceCandidateAuditSchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MIGRATION_PATH.read_text(encoding="utf-8")

    def test_candidate_is_scoped_to_an_existing_workspace_tab(self):
        self.assertRegex(self.source, r"create table public\.source_candidates\s*\(")
        for column in [
            "workspace_id uuid not null",
            "tab_id uuid not null",
            "url text not null",
            "title text not null",
            "status text not null default 'pending'",
            "submitted_by uuid not null",
            "reviewed_by uuid",
            "reviewed_at timestamptz",
        ]:
            self.assertIn(column, self.source)
        self.assertRegex(
            self.source,
            r"foreign key \(workspace_id, tab_id\)\s+references public\.workspace_tabs\(workspace_id, id\)",
        )
        self.assertIn("check (status in ('pending', 'approved', 'rejected'))", self.source)
        self.assertIn("unique (workspace_id, tab_id, url)", self.source)

    def test_audit_rows_capture_actor_transition_reason_and_snapshot(self):
        self.assertRegex(
            self.source, r"create table public\.source_candidate_audits\s*\("
        )
        for column in [
            "source_candidate_id uuid not null",
            "workspace_id uuid not null",
            "tab_id uuid not null",
            "actor_user_id uuid not null",
            "action text not null",
            "old_status text",
            "new_status text not null",
            "reason text",
            "snapshot jsonb not null",
            "created_at timestamptz not null default now()",
        ]:
            self.assertIn(column, self.source)
        self.assertRegex(
            self.source,
            re.compile(
                r"foreign key \(workspace_id, tab_id, source_candidate_id\).*?"
                r"references public\.source_candidates\(workspace_id, tab_id, id\)",
                re.S,
            ),
        )

    def test_database_trigger_writes_creation_and_status_change_audits(self):
        self.assertRegex(
            self.source,
            re.compile(
                r"create function public\.audit_source_candidate_change\(\).*?"
                r"security definer.*?insert into public\.source_candidate_audits",
                re.S,
            ),
        )
        self.assertIn("if tg_op = 'INSERT' then", self.source)
        self.assertIn("new.status is distinct from old.status", self.source)
        self.assertRegex(
            self.source,
            r"create trigger audit_source_candidate_change\s+after insert or update of status",
        )

    def test_rls_keeps_candidates_member_scoped_and_audits_read_only(self):
        self.assertIn(
            "alter table public.source_candidates enable row level security;", self.source
        )
        self.assertIn(
            "alter table public.source_candidate_audits enable row level security;",
            self.source,
        )
        self.assertRegex(
            self.source,
            re.compile(
                r'create policy "workspace members manage source_candidates".*?'
                r"using \(public\.is_workspace_member\(workspace_id\)\).*?"
                r"with check \(public\.is_workspace_member\(workspace_id\)\)",
                re.S,
            ),
        )
        self.assertRegex(
            self.source,
            re.compile(
                r'create policy "workspace members read source_candidate_audits".*?'
                r"for select.*?using \(public\.is_workspace_member\(workspace_id\)\)",
                re.S,
            ),
        )
        self.assertNotRegex(
            self.source,
            r'create policy "[^"]*(?:manage|insert|update|delete)[^"]*source_candidate_audits"',
        )

    def test_migration_is_additive_and_does_not_replace_existing_rls(self):
        existing_tables = [
            "workspaces",
            "workspace_members",
            "workspace_tabs",
            "competitors",
            "dimensions",
            "evidence",
            "evidence_dimensions",
            "insights",
            "insight_competitors",
            "insight_dimensions",
            "insight_evidence",
            "matrix_cells",
        ]
        for table in existing_tables:
            self.assertNotRegex(
                self.source,
                rf"(?:drop|alter)\s+table\s+(?:if exists\s+)?public\.{table}\b",
            )
        self.assertNotRegex(self.source, r"drop\s+policy\b")
        self.assertNotRegex(self.source, r"disable\s+row\s+level\s+security")


if __name__ == "__main__":
    unittest.main()
