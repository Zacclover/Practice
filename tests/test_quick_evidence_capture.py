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
        source_url_input = re.search(
            r'<input[^>]*id="quickEvidenceSourceUrl"[^>]*>', self.source
        )
        self.assertIsNotNone(source_url_input)
        self.assertNotIn('required', source_url_input.group(0))
        self.assertRegex(self.source, r'id="quickEvidenceSourceType"[^>]*required')

    def test_quick_save_allows_a_fact_without_a_source_link(self):
        self.assertIn("const normalizedSourceUrl = sourceUrl", self.source)
        self.assertIn("if (!fact || !sourceType)", self.source)
        self.assertIn("const sourceMarkup = normalizedSourceUrl", self.source)

    def test_quick_form_accepts_pasted_screenshots(self):
        self.assertIn('id="quickEvidencePasteArea"', self.source)
        self.assertIn("quickEvidencePasteArea.addEventListener('paste'", self.source)
        self.assertIn('quickEvidenceFiles.push(...pastedImages);', self.source)
        self.assertIn('event.clipboardData.items', self.source)

    def test_quick_source_type_selector_reuses_the_form_control_contract(self):
        self.assertIn('input,\n    textarea,\n    select {', self.source)
        self.assertIn('input:focus,\n    textarea:focus,\n    select:focus {', self.source)

    def test_matrix_no_longer_offers_manual_supplement_content(self):
        self.assertNotIn('自主补充内容', self.source)
        self.assertNotIn('class="matrix-input"', self.source)
        self.assertNotIn("comparisonContainer.addEventListener('input'", self.source)

    def test_matrix_uses_a_numeric_evidence_badge_instead_of_a_text_header(self):
        self.assertIn('class="matrix-evidence-count"', self.source)
        self.assertIn('data-linked-dimension-id=', self.source)
        self.assertNotIn('证据内容（${linkedEvidence.length}）', self.source)

    def test_quick_capture_entries_only_reveal_in_their_context(self):
        self.assertIn('quick-evidence-trigger', self.source)
        self.assertIn('.competitor-evidence:hover .quick-evidence-trigger', self.source)
        self.assertIn('.comparison-table td:hover .matrix-coverage-gap', self.source)

    def test_quick_save_creates_a_normal_evidence_record_with_source_metadata(self):
        self.assertIn("quickEvidenceForm.addEventListener('submit', async event =>", self.source)
        self.assertIn('sourceUrl: normalizedSourceUrl', self.source)
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
