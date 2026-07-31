import re
import unittest
from pathlib import Path


INDEX_PATH = Path(__file__).resolve().parents[1] / "index.html"


class EvidenceSearchContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = INDEX_PATH.read_text(encoding="utf-8")

    def test_search_has_an_explicit_entry_and_a_command_palette_dialog(self):
        self.assertRegex(
            self.source,
            r'<button[^>]*id="evidenceSearchTrigger"[^>]*>.*?搜索证据',
            re.S,
        )
        self.assertIn('id="evidenceSearchDialog"', self.source)
        self.assertIn('id="evidenceSearchInput"', self.source)
        self.assertIn('id="evidenceSearchResults"', self.source)

    def test_search_can_be_opened_with_command_or_control_k(self):
        self.assertIn("event.key.toLowerCase() === 'k'", self.source)
        self.assertIn('event.metaKey || event.ctrlKey', self.source)
        self.assertIn('openEvidenceSearchDialog()', self.source)

    def test_search_matches_evidence_content_and_supports_context_filters(self):
        self.assertIn('function getFilteredEvidenceSearchResults()', self.source)
        self.assertIn('evidence.title', self.source)
        self.assertIn('evidence.content', self.source)
        self.assertIn('evidence.sourceUrl', self.source)
        self.assertIn('id="evidenceSearchCompetitorFilter"', self.source)
        self.assertIn('id="evidenceSearchDimensionFilter"', self.source)
        self.assertIn('id="evidenceSearchSourceTypeFilter"', self.source)

    def test_result_opens_the_existing_evidence_detail_dialog(self):
        self.assertIn('data-evidence-search-result-id=', self.source)
        self.assertIn('openEvidenceDetail(evidenceIndex);', self.source)


if __name__ == '__main__':
    unittest.main()
