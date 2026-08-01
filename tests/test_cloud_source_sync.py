import re
import unittest
from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "index.html").read_text(encoding="utf-8")


class CloudSourceSyncTests(unittest.TestCase):
    def test_rest_requests_use_only_public_key_and_bearer_user_token(self):
        self.assertIn("async function cloudRestRequest", SOURCE)
        self.assertIn("apikey: config.publishableKey", SOURCE)
        self.assertIn("Authorization: `Bearer ${accessToken}`", SOURCE)
        self.assertNotRegex(SOURCE.lower(), r"service_role|service-role|secret[_-]?key")

    def test_sync_resolves_workspace_then_upserts_fk_prerequisites_before_sources(self):
        function = re.search(
            r"async function synchronizeCloudSourceCapture\(profile, accessToken\) \{(?P<body>.*?)\n    \}",
            SOURCE,
            re.S,
        )
        self.assertIsNotNone(function)
        body = function.group("body")
        ordered_markers = [
            "resolveCloudWorkspace",
            'cloudRestRequest("workspace_tabs"',
            'cloudRestRequest("competitors"',
            'cloudRestRequest("competitor_sources"',
            'cloudRestRequest(`source_capture_candidates?',
        ]
        positions = [body.find(marker) for marker in ordered_markers]
        self.assertTrue(all(position >= 0 for position in positions), positions)
        self.assertEqual(positions, sorted(positions))

    def test_cloud_source_crud_and_pending_queue_are_wired(self):
        for function_name in [
            "createCloudCompetitorSource",
            "updateCloudCompetitorSource",
            "deleteCloudCompetitorSource",
        ]:
            self.assertIn(f"async function {function_name}", SOURCE)
        self.assertIn("status=eq.pending", SOURCE)
        self.assertIn("sourceCaptureState.candidates =", SOURCE)
        self.assertIn("sourceCaptureState.cloudSynced = true", SOURCE)
        self.assertIn("云端已同步", SOURCE)
        self.assertIn("本机保存", SOURCE)

    def test_sync_scope_never_writes_research_outputs(self):
        function = re.search(
            r"async function synchronizeCloudSourceCapture\(profile, accessToken\) \{(?P<body>.*?)\n    \}",
            SOURCE,
            re.S,
        )
        self.assertIsNotNone(function)
        body = function.group("body")
        for forbidden_table in ["evidence", "dimensions", "matrix_cells", "insights"]:
            self.assertNotIn(f'cloudRestRequest("{forbidden_table}"', body)


if __name__ == "__main__":
    unittest.main()
