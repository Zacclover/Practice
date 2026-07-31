import re
import unittest
from pathlib import Path


INDEX_PATH = Path(__file__).resolve().parents[1] / "index.html"


class MatrixEvidenceRevealContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = INDEX_PATH.read_text(encoding="utf-8")

    def test_evidence_count_is_a_compact_non_interactive_cell_corner_marker(self):
        self.assertIn('class="matrix-evidence-count"', self.source)
        self.assertRegex(
            self.source,
            r'<span\s+class="matrix-evidence-count"[^>]*>\s*\$\{linkedEvidence.length\}',
        )
        self.assertIn('position: absolute;', self.source)
        self.assertIn('right: 0;', self.source)
        self.assertIn('min-width: 40px;', self.source)

    def test_evidence_count_does_not_open_or_target_linked_evidence(self):
        self.assertNotIn('data-linked-dimension-id=', self.source)
        self.assertNotIn('data-linked-competitor-id=', self.source)
        self.assertNotIn("button[data-linked-dimension-id]", self.source)

    def test_coarse_pointer_has_a_cell_scoped_reveal_path(self):
        self.assertIn(
            "evidenceCell?.querySelector('.matrix-quick-capture')",
            self.source,
        )


if __name__ == "__main__":
    unittest.main()
