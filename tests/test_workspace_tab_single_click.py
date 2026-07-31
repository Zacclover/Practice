from pathlib import Path
import unittest


class WorkspaceTabSingleClickContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (Path(__file__).resolve().parents[1] / "index.html").read_text(
            encoding="utf-8"
        )

    def test_tab_select_is_not_intercepted_for_touch_context_reveal(self):
        """点击 Tab 本身应直接交给 Tab 激活委托，不先用于展开工具按钮。"""
        self.assertIn("if (directControl) {\n        clearTouchContexts(surface);\n        return;\n      }", self.source)
        self.assertNotIn("!directControl.matches('.workspace-tab-select')", self.source)


if __name__ == "__main__":
    unittest.main()
