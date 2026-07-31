import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FUNCTION = ROOT / "functions" / "cloud-config.js"


class CloudConfigFunctionTests(unittest.TestCase):
    def invoke(self, env):
        with tempfile.TemporaryDirectory() as temporary_directory:
            module_path = Path(temporary_directory) / "cloud-config.mjs"
            module_path.write_text(FUNCTION.read_text(encoding="utf-8"), encoding="utf-8")
            runner = """
                const { onRequest } = await import(process.argv[1]);
                const response = await onRequest({ env: JSON.parse(process.argv[2]) });
                console.log(JSON.stringify({
                    status: response.status,
                    headers: Object.fromEntries(response.headers.entries()),
                    body: await response.text(),
                }));
            """
            result = subprocess.run(
                ["node", "--input-type=module", "--eval", runner, module_path.as_uri(), json.dumps(env)],
                check=True,
                capture_output=True,
                text=True,
            )
        return json.loads(result.stdout)

    def test_valid_environment_returns_runtime_config_javascript(self):
        result = self.invoke({
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "public-key",
        })

        self.assertEqual(result["status"], 200)
        self.assertEqual(result["headers"]["cache-control"], "no-store")
        self.assertEqual(result["headers"]["content-type"], "application/javascript; charset=utf-8")
        self.assertEqual(
            result["body"],
            'window.COMPETITOR_INSIGHTS_CLOUD_CONFIG = {"url":"https://example.supabase.co","publishableKey":"public-key"};',
        )

    def test_serialization_cannot_break_out_of_javascript_data(self):
        result = self.invoke({
            "SUPABASE_URL": "https://example.supabase.co/path?<tag>&value",
            "SUPABASE_PUBLISHABLE_KEY": 'key";</script><script>alert(1)</script>\u2028next',
        })

        self.assertNotIn("</script>", result["body"])
        self.assertNotIn("<tag>", result["body"])
        self.assertNotIn("\u2028", result["body"])
        self.assertIn("\\u003c/script\\u003e", result["body"])
        self.assertIn("\\u2028", result["body"])

    def test_missing_or_invalid_environment_returns_harmless_javascript(self):
        invalid_environments = [
            {},
            {"SUPABASE_URL": "http://example.supabase.co", "SUPABASE_PUBLISHABLE_KEY": "public-key"},
            {"SUPABASE_URL": "not a URL", "SUPABASE_PUBLISHABLE_KEY": "public-key"},
            {"SUPABASE_URL": "https://example.supabase.co", "SUPABASE_PUBLISHABLE_KEY": "   "},
        ]

        for environment in invalid_environments:
            with self.subTest(environment=environment):
                result = self.invoke(environment)
                self.assertEqual(result["status"], 200)
                self.assertEqual(result["headers"]["cache-control"], "no-store")
                self.assertEqual(result["body"], "")
                self.assertNotIn("COMPETITOR_INSIGHTS_CLOUD_CONFIG", result["body"])


if __name__ == "__main__":
    unittest.main()
