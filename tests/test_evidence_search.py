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
            r'<button[^>]*id="evidenceSearchTrigger"[^>]*aria-label="搜索证据"',
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

    def test_search_entry_reuses_section_header_actions_layout(self):
        self.assertIn('class="competitor-section-header comparison-header"', self.source)
        self.assertRegex(
            self.source,
            r'<button[^>]*class="[^"]*evidence-search-trigger[^"]*"',
        )

    def test_search_entry_is_an_icon_only_control(self):
        self.assertRegex(
            self.source,
            r'<button[^>]*id="evidenceSearchTrigger"[^>]*aria-label="搜索证据"[^>]*>\s*<svg',
        )
        self.assertNotIn('id="evidenceSearchShortcut"', self.source)

    def test_dialog_has_an_explicit_icon_close_control(self):
        self.assertIn('id="evidenceSearchClose"', self.source)
        self.assertIn('aria-label="关闭搜索证据"', self.source)
        self.assertIn('evidenceSearchClose.addEventListener', self.source)

    def test_search_result_uses_typed_tags_and_highlights_query_matches(self):
        self.assertIn('evidence-search-tag--competitor', self.source)
        self.assertIn('evidence-search-tag--dimension', self.source)
        self.assertIn('evidence-search-tag--source', self.source)
        self.assertIn('function highlightEvidenceSearchText', self.source)
        self.assertIn('evidence-search-highlight', self.source)
        self.assertIn('clip-path: polygon(7px 0', self.source)

    def test_search_filters_are_multi_select_controls_like_insight_filters(self):
        for filter_id, control_id in (
            ('evidenceSearchCompetitorFilter', 'evidenceSearchCompetitorFilterControl'),
            ('evidenceSearchDimensionFilter', 'evidenceSearchDimensionFilterControl'),
            ('evidenceSearchSourceTypeFilter', 'evidenceSearchSourceTypeFilterControl'),
        ):
            self.assertIn(f'<select id="{filter_id}" multiple hidden>', self.source)
            self.assertIn(f'id="{control_id}"', self.source)
        self.assertIn('function renderEvidenceSearchFilterControl(', self.source)

    def test_result_grid_never_centers_its_content(self):
        self.assertIn('justify-content: flex-start !important;', self.source)
        self.assertIn('align-content: start;', self.source)

    def test_input_focus_encloses_its_search_icon(self):
        self.assertIn('.evidence-search-input-wrap:focus-within', self.source)


if __name__ == '__main__':
    unittest.main()
