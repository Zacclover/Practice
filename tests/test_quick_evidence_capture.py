import re
import unittest
from pathlib import Path


INDEX_PATH = Path(__file__).resolve().parents[1] / "index.html"


class QuickEvidenceCaptureContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = INDEX_PATH.read_text(encoding="utf-8")

    def test_competitor_cards_and_matrix_gaps_offer_a_quick_capture_path(self):
        self.assertIn('data-action="quick-evidence"', self.source)
        self.assertIn('data-quick-evidence-competitor-id=', self.source)
        self.assertIn('data-quick-evidence-dimension-id=', self.source)
        self.assertIn('function openQuickEvidenceDialog(competitorId, dimensionId = null)', self.source)

    def test_quick_form_keeps_the_required_capture_fields_small_and_explicit(self):
        self.assertIn('id="quickEvidenceDialog"', self.source)
        self.assertIn('id="quickEvidenceFact"', self.source)
        self.assertIn('id="quickEvidenceSourceUrl"', self.source)
        self.assertIn('id="quickEvidenceSourceType"', self.source)
        self.assertIn('id="quickEvidenceImage"', self.source)
        self.assertRegex(self.source, r'id="quickEvidenceFact"[^>]*required')
        self.assertRegex(self.source, r'id="quickEvidenceSourceUrl"[^>]*required')
        self.assertRegex(self.source, r'id="quickEvidenceSourceType"[^>]*required')

    def test_quick_save_creates_a_normal_evidence_record_with_source_metadata(self):
        self.assertIn("quickEvidenceForm.addEventListener('submit', async event =>", self.source)
        self.assertIn('sourceUrl: normalizeWebsiteUrl(sourceUrl)', self.source)
        self.assertIn('sourceType,', self.source)
        self.assertIn('dimensionIds: Array.from(selectedQuickEvidenceDimensionIds)', self.source)
        self.assertIn('persistEvidence();', self.source)
        self.assertIn('render();', self.source)

    def test_existing_evidence_remains_the_only_insight_reference_subject(self):
        quick_submit = re.search(
            r"quickEvidenceForm\.addEventListener\('submit', async event => \{(?P<body>.*?)\n\s*\}\);",
            self.source,
            re.S,
        )
        self.assertIsNotNone(quick_submit)
        assert quick_submit is not None
        self.assertIn('evidenceItems.push(evidence);', quick_submit.group('body'))
        self.assertNotIn('insights.push(', quick_submit.group('body'))


if __name__ == '__main__':
    unittest.main()
