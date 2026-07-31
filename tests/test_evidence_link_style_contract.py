import re
import unittest
from pathlib import Path


INDEX_PATH = Path(__file__).resolve().parents[1] / "index.html"


class EvidenceLinkStyleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = INDEX_PATH.read_text(encoding="utf-8")

    def test_matrix_evidence_has_no_black_outline(self):
        rule = re.search(r'\.matrix-evidence-line,\s*\.insight-evidence-link\s*\{(?P<body>.*?)\n\s*\}', self.source, re.S)
        self.assertIsNotNone(rule)
        assert rule is not None
        self.assertIn('border: 0 !important;', rule.group('body'))
        self.assertIn('border-left: 3px solid var(--orange) !important;', rule.group('body'))

    def test_insight_evidence_reuses_matrix_evidence_surface(self):
        rule = re.search(r'\.matrix-evidence-line,\s*\.insight-evidence-link\s*\{(?P<body>.*?)\n\s*\}', self.source, re.S)
        self.assertIsNotNone(rule)
        assert rule is not None
        body = rule.group('body')
        self.assertIn('background: var(--gray-100);', body)
        self.assertIn('color: var(--ink);', body)
        self.assertIn('text-decoration: none;', body)


if __name__ == '__main__':
    unittest.main()
