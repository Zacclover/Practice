import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT / "supabase" / "migrations" / "20260731000000_cloud_workspace_foundation.sql"
)


class CloudWorkspaceSchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MIGRATION_PATH.read_text(encoding="utf-8")

    def test_workspace_core_keeps_tab_research_entities_and_relationships_normalized(self):
        required_tables = [
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
        for table in required_tables:
            self.assertRegex(
                self.source,
                rf"create table public\.{table}\s*\(",
                f"缺少 public.{table}。",
            )

        self.assertIn("unique (workspace_id, user_id)", self.source)
        self.assertIn("unique (evidence_id, dimension_id)", self.source)
        self.assertIn("unique (insight_id, competitor_id)", self.source)
        self.assertIn("unique (insight_id, dimension_id)", self.source)
        self.assertIn("unique (insight_id, evidence_id)", self.source)
        self.assertIn("unique (dimension_id, competitor_id)", self.source)

    def test_every_product_table_has_row_level_security_and_member_scoped_policies(self):
        protected_tables = [
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
        for table in protected_tables:
            self.assertIn(f"alter table public.{table} enable row level security;", self.source)
            self.assertRegex(
                self.source,
                rf"create policy \"workspace members manage {table}\"\s+on public\.{table}",
            )

        self.assertRegex(
            self.source,
            r"create function public\.is_workspace_member\(target_workspace_id uuid\).*?security definer",
            re.S,
        )
        self.assertIn("auth.uid()", self.source)

    def test_workspace_creator_becomes_owner_member_through_database_trigger(self):
        self.assertRegex(
            self.source,
            r"create function public\.add_workspace_owner\(\).*?insert into public\.workspace_members",
            re.S,
        )
        self.assertIn(
            "create trigger on_workspace_created\n"
            "after insert on public.workspaces\n"
            "for each row execute function public.add_workspace_owner();",
            self.source,
        )

    def test_evidence_and_insight_content_fields_preserve_current_research_semantics(self):
        self.assertIn("content_html text not null default ''", self.source)
        self.assertIn("images jsonb not null default '[]'::jsonb", self.source)
        self.assertIn("fact_signals text not null default ''", self.source)
        self.assertIn("common_pattern text not null default ''", self.source)
        self.assertIn("key_difference text not null default ''", self.source)
        self.assertIn("opportunity_hypothesis text not null default ''", self.source)
        self.assertIn("action_recommendation text not null default ''", self.source)


if __name__ == "__main__":
    unittest.main()
