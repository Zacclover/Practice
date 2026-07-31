import re
import unittest
from pathlib import Path


INDEX_PATH = Path(__file__).resolve().parents[1] / "index.html"


class MatrixEvidenceRevealContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = INDEX_PATH.read_text(encoding="utf-8")

    def test_evidence_count_is_a_compact_cell_corner_control(self):
        self.assertIn('class="matrix-evidence-count"', self.source)
        self.assertIn('position: absolute;', self.source)
        self.assertIn('right: 0;', self.source)
        self.assertIn('min-width: 40px;', self.source)

    def test_evidence_count_opens_the_linked_evidence_collection(self):
        self.assertIn('data-linked-dimension-id=', self.source)
        self.assertIn('data-linked-competitor-id=', self.source)
        self.assertIn("button[data-linked-dimension-id]", self.source)

    def test_coarse_pointer_has_a_cell_scoped_reveal_path(self):
        self.assertIn(
            "evidenceCell?.querySelector('.matrix-evidence-count')",
            self.source,
        )


if __name__ == "__main__":
    unittest.main()
