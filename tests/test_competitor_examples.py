import re
import unittest
from pathlib import Path


INDEX_PATH = Path(__file__).resolve().parents[1] / "index.html"


class CompetitorExamplesContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = INDEX_PATH.read_text(encoding="utf-8")

    def test_clear_examples_button_is_secondary_and_precedes_add_button(self):
        actions = re.search(
            r'<div class="hero-actions">(?P<body>.*?)</div>',
            self.source,
            re.S,
        )
        self.assertIsNotNone(actions)
        body = actions.group("body")
        clear_position = body.find('id="clearExamplesButton"')
        add_position = body.find('id="addButton"')
        self.assertGreaterEqual(clear_position, 0)
        self.assertGreater(add_position, clear_position)
        self.assertRegex(
            body,
            r'(?s)<button[^>]*class="secondary"[^>]*id="clearExamplesButton"[^>]*>.*?清空示例',
        )

    def test_fresh_workspace_uses_sample_content_without_overwriting_stored_data(self):
        self.assertIn("function createSampleWorkspaceTab", self.source)
        migration = re.search(
            r'function migrateLegacyWorkspaceData\(\) \{(?P<body>.*?)\n    \}',
            self.source,
            re.S,
        )
        self.assertIsNotNone(migration)
        body = migration.group("body")
        self.assertIn("hasLegacyWorkspaceData", body)
        self.assertIn("createSampleWorkspaceTab", body)
        self.assertIn("readStoredArray(storageKey)", body)

    def test_sample_data_carries_is_sample_marker(self):
        sample_fn = re.search(
            r'function createSampleWorkspaceTab\(name = [\'"]默认空间[\'"]\) \{(?P<body>.*?)\n    \}\n\n',
            self.source,
            re.S,
        )
        self.assertIsNotNone(sample_fn)
        body = sample_fn.group("body")
        self.assertRegex(body, r"isSample:\s*true")
        self.assertIn("sampleValues", body)

    def test_clear_button_visibility_tracks_remaining_sample_data(self):
        self.assertIn("function getCurrentSampleCount", self.source)
        render = re.search(
            r'function render\(\) \{(?P<body>.*?)\n    \}\n\n    /\* ==============================\n       渲染竞品横向对比矩阵',
            self.source,
            re.S,
        )
        self.assertIsNotNone(render)
        self.assertRegex(
            render.group("body"),
            r'clearExamplesButton\.hidden\s*=\s*getCurrentSampleCount\(\)\s*===\s*0',
        )

    def test_clear_examples_only_removes_sample_marked_data(self):
        handler = re.search(
            r'clearExamplesButton\.addEventListener\(\s*[\'\"]click[\'\"],\s*\(\) => \{(?P<body>.*?)\n    \}\);',
            self.source,
            re.S,
        )
        self.assertIsNotNone(handler)
        body = handler.group("body")
        self.assertIn("window.confirm", body)
        # 只删除带 isSample 标记的数据，而不是清空整个数组
        self.assertRegex(
            body,
            r'competitors\s*=\s*competitors\.filter\(\s*item\s*=>\s*item\.isSample\s*!==\s*true\s*\)',
        )
        self.assertRegex(
            body,
            r'evidenceItems\s*=\s*evidenceItems\.filter\(\s*item\s*=>\s*item\.isSample\s*!==\s*true\s*\)',
        )
        self.assertRegex(
            body,
            r'insights\s*=\s*insights\.filter\(\s*item\s*=>\s*item\.isSample\s*!==\s*true\s*\)',
        )
        self.assertIn("sampleValues", body)
        self.assertIn("persistWorkspaceState()", body)
        self.assertIn("render()", body)

    def test_editing_sample_data_unmarks_is_sample(self):
        # 竞品编辑后移除 isSample
        self.assertRegex(
            self.source,
            r'if\s*\(\s*editingIndex\s*!==\s*null\s*\)\s*\{\s*delete\s+competitor\.isSample;\s*\}',
        )
        # 证据编辑后移除 isSample
        self.assertRegex(
            self.source,
            r'if\s*\(\s*previousEvidence\s*&&\s*previousEvidence\.isSample\s*===\s*true\s*\)\s*\{\s*delete\s+evidence\.isSample;\s*\}',
        )
        # 洞察编辑后移除 isSample
        self.assertRegex(
            self.source,
            r'if\s*\(\s*existingInsight\s*&&\s*existingInsight\.isSample\s*===\s*true\s*\)\s*\{\s*delete\s+candidate\.isSample;\s*\}',
        )
        # 维度编辑后移除 isSample
        self.assertRegex(
            self.source,
            r'if\s*\(\s*dimension\.isSample\s*===\s*true\s*\)\s*\{\s*delete\s+dimension\.isSample;',
        )
        # 矩阵单元格输入后移除 sampleValues 标记
        self.assertRegex(
            self.source,
            r'comparisonData\.sampleValues\[dimensionId\]\[competitorId\]',
        )


if __name__ == "__main__":
    unittest.main()
