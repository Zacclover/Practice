import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260802000000_cloud_workspace_sync_rpcs.sql"


class CloudWorkspaceSyncRpcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MIGRATION.read_text(encoding="utf-8")

    def test_atomic_initial_import_and_tab_mutation_rpcs_are_security_definer(self):
        for name in ("import_initial_workspace_snapshot", "apply_workspace_tab_mutations"):
            self.assertRegex(
                self.source,
                rf"create or replace function public\.{name}\([\s\S]*?security definer\s+set search_path = ''",
            )
            self.assertRegex(self.source, rf"revoke all on function public\.{name}")
            self.assertRegex(self.source, rf"grant execute on function public\.{name}.*?to authenticated")

    def test_rpcs_validate_authenticated_membership_and_serialize_workspace_changes(self):
        self.assertIn("auth.uid()", self.source)
        self.assertIn("public.is_workspace_member", self.source)
        self.assertIn("for update", self.source.lower())
        self.assertIn("jsonb_array_elements", self.source)
        self.assertNotRegex(self.source.lower(), r"service_role|secret[_-]?key")

    def test_owner_workspace_uniqueness_is_database_enforced(self):
        self.assertIn("unique index workspaces_owner_user_id_unique_idx", self.source)
        self.assertIn("create or replace function public.resolve_user_workspace", self.source)


if __name__ == "__main__":
    unittest.main()
