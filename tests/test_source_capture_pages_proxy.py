import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROXY = ROOT / "functions" / "api" / "source-capture" / "[[path]].js"
MANUAL_CAPTURE = ROOT / "functions" / "api" / "source-capture" / "manual-capture.js"


class SourceCapturePagesProxyContractTests(unittest.TestCase):
    def test_same_origin_proxy_route_exists_and_does_not_publish_an_open_proxy(self):
        self.assertTrue(PROXY.is_file(), "Pages 同源 source-capture 代理路由必须存在")
        self.assertTrue(MANUAL_CAPTURE.is_file(), "手动抓取必须具备精确同源 Pages 路由")
        source = PROXY.read_text(encoding="utf-8")
        exact_route = MANUAL_CAPTURE.read_text(encoding="utf-8")
        self.assertIn("export async function onRequest", source)
        self.assertIn("forwardSourceCaptureRequest", exact_route)
        self.assertIn("manual-capture", source)
        self.assertIn("candidate-attachments", source)
        self.assertIn("capture-runs", source)
        self.assertIn('new Set(["DELETE", "OPTIONS"])', source)
        self.assertNotIn("request.url", source)


if __name__ == "__main__":
    unittest.main()
