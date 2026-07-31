import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
EXAMPLE = ROOT / "cloud-config.example.js"


class CloudRuntimeConfigContractTests(unittest.TestCase):
    def test_example_only_contains_public_runtime_placeholders(self):
        source = EXAMPLE.read_text(encoding="utf-8")
        self.assertIn("window.COMPETITOR_INSIGHTS_CLOUD_CONFIG", source)
        self.assertIn("SUPABASE_URL", source)
        self.assertIn("SUPABASE_PUBLISHABLE_KEY", source)
        self.assertNotRegex(source.lower(), r"service_role|secret[_-]?key|database[_-]?password")

    def test_page_loads_optional_cloud_config_synchronously_before_application_code(self):
        source = INDEX.read_text(encoding="utf-8")
        config_script = '<script src="/cloud-config"></script>'
        example_script = source.find(config_script)
        application_script = source.find("<script>")
        self.assertGreaterEqual(example_script, 0)
        self.assertGreater(application_script, example_script)
        self.assertIn("function getCloudRuntimeConfig()", source)
        self.assertIn("COMPETITOR_INSIGHTS_CLOUD_CONFIG", source)

    def test_unconfigured_cloud_mode_keeps_local_first_startup_safe(self):
        source = INDEX.read_text(encoding="utf-8")
        config_function = re.search(
            r"function getCloudRuntimeConfig\(\) \{(?P<body>.*?)\n    \}", source, re.S
        )
        self.assertIsNotNone(config_function)
        body = config_function.group("body")
        self.assertIn("enabled: false", body)
        self.assertIn("url", body)
        self.assertIn("publishableKey", body)


if __name__ == "__main__":
    unittest.main()
