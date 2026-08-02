import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260802000000_cloud_workspace_sync_rpcs.sql"
BOOTSTRAP_REPAIR = ROOT / "supabase" / "migrations" / "20260802010000_workspace_bootstrap_rls_repair.sql"


class CloudWorkspaceSyncRpcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MIGRATION.read_text(encoding="utf-8")
        cls.bootstrap_repair = BOOTSTRAP_REPAIR.read_text(encoding="utf-8")

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

    def test_bootstrap_has_a_minimal_owner_insert_policy_separate_from_member_access(self):
        self.assertRegex(
            self.bootstrap_repair,
            r'create policy "authenticated users bootstrap own workspace"[\s\S]*?'
            r'for insert\s+to authenticated\s+with check \(owner_user_id = auth\.uid\(\)\)',
        )
        self.assertRegex(
            self.bootstrap_repair,
            r'create policy "workspace members read workspaces"[\s\S]*?for select',
        )

    def test_bootstrap_rpc_does_not_require_membership_via_conflict_update(self):
        function = re.search(
            r"create or replace function public\.resolve_user_workspace\([\s\S]*?\n\$\$;",
            self.bootstrap_repair,
        )
        self.assertIsNotNone(function)
        body = function.group(0)
        self.assertIn("security definer", body.lower())
        self.assertIn("owner_user_id = auth.uid()", body)
        self.assertIn("exception when unique_violation", body.lower())
        self.assertNotIn("on conflict", body.lower())


if __name__ == "__main__":
    unittest.main()
