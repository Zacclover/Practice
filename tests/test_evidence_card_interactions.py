import unittest
from pathlib import Path


INDEX_PATH = Path(__file__).resolve().parents[1] / "index.html"


class EvidenceCardInteractionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = INDEX_PATH.read_text(encoding="utf-8")

    def test_evidence_tile_click_opens_its_detail_without_context_activation(self):
        self.assertIn('data-evidence-action="view"', self.source)
        self.assertIn("openEvidenceDetail(evidenceIndex);", self.source)
        self.assertIn(
            "if (target.closest?.('.evidence-tile')) {\n        return null;\n      }",
            self.source,
        )

    def test_cancelling_evidence_edit_returns_the_competitor_card_to_neutral_state(self):
        self.assertIn("evidenceDialog.addEventListener('close', () => {", self.source)
        self.assertIn("const activeCompetitorCard = document.activeElement?.closest(", self.source)
        self.assertIn("'.competitor-card'", self.source)
        self.assertIn("document.activeElement.blur();", self.source)


if __name__ == '__main__':
    unittest.main()
