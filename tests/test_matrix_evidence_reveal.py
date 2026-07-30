import re
import unittest
from pathlib import Path


INDEX_PATH = Path(__file__).resolve().parents[1] / "index.html"


class MatrixEvidenceRevealContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = INDEX_PATH.read_text(encoding="utf-8")

    def test_view_all_is_hidden_by_default(self):
        rules = re.findall(
            r"\.matrix-evidence-link\s*\{(?P<body>.*?)\n\s*\}",
            self.source,
            re.S,
        )
        self.assertTrue(rules)
        hidden_rule = next(
            (body for body in rules if "opacity: 0" in body),
            None,
        )
        self.assertIsNotNone(hidden_rule)
        assert hidden_rule is not None
        self.assertIn("pointer-events: none", hidden_rule)

    def test_view_all_reveals_only_for_its_cell_hover_or_focus(self):
        self.assertIn(
            ".comparison-table td:hover .matrix-evidence-link",
            self.source,
        )
        self.assertIn(
            ".comparison-table td:focus-within .matrix-evidence-link",
            self.source,
        )
        self.assertIn("pointer-events: auto", self.source)

    def test_coarse_pointer_has_a_cell_scoped_reveal_path(self):
        self.assertIn(
            ".comparison-table td.is-context-active .matrix-evidence-link",
            self.source,
        )
        self.assertIn(
            "evidenceCell?.querySelector('.matrix-evidence-link')",
            self.source,
        )


if __name__ == "__main__":
    unittest.main()
