import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROXY = ROOT / "functions" / "api" / "source-capture" / "[[path]].js"


class SourceCapturePagesProxyContractTests(unittest.TestCase):
    def test_same_origin_proxy_route_exists_and_does_not_publish_an_open_proxy(self):
        self.assertTrue(PROXY.is_file(), "Pages 同源 source-capture 代理路由必须存在")
        source = PROXY.read_text(encoding="utf-8")
        self.assertIn("export async function onRequest", source)
        self.assertIn("manual-capture", source)
        self.assertIn("candidate-attachments", source)
        self.assertNotIn("request.url", source)


if __name__ == "__main__":
    unittest.main()
