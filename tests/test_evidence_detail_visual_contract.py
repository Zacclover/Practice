import unittest
from pathlib import Path


INDEX_PATH = Path(__file__).resolve().parents[1] / "index.html"


class EvidenceDetailVisualContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = INDEX_PATH.read_text(encoding="utf-8")

    def test_detail_dialog_uses_the_industrial_dialog_and_content_surface_tokens(self):
        self.assertIn('.detail-dialog {\n      width: min(960px, calc(100% - 32px));', self.source)
        self.assertIn('border: 2px solid var(--line-strong);', self.source)
        self.assertIn('border-radius: 0;', self.source)
        self.assertIn('background: var(--white);', self.source)

    def test_detail_has_clear_editorial_header_metadata_and_section_labels(self):
        self.assertIn('class="detail-header"', self.source)
        self.assertIn('class="detail-kicker"', self.source)
        self.assertIn('class="detail-section-label"', self.source)
        self.assertIn('class="detail-meta-item"', self.source)

    def test_detail_dimension_tag_is_a_standard_two_corner_cut_rectangle(self):
        self.assertIn('.detail-dimension-tag {', self.source)
        self.assertIn(
            'clip-path: polygon(6px 0, 100% 0, 100% calc(100% - 6px), '
            'calc(100% - 6px) 100%, 0 100%, 0 6px);',
            self.source,
        )

    def test_detail_uses_flat_image_and_no_screenshot_states_instead_of_rounded_cards(self):
        self.assertIn('class="detail-image"', self.source)
        self.assertIn('class="detail-image-empty"', self.source)
        self.assertIn('>未附截图<', self.source)
        self.assertIn('border-radius: 0;', self.source)
    def test_detail_preview_is_the_single_entry_for_evidence_editing(self):
        self.assertIn('class="actions detail-footer"', self.source)
        self.assertIn('详情操作位于正文之后，避免遮挡既有标题与元数据', self.source)
        self.assertNotIn('.detail-edit-button { position: absolute;', self.source)
        self.assertIn('justify-content: space-between;', self.source)
        self.assertIn('detailEvidenceIndex = evidenceIndex;', self.source)
        self.assertIn('openEvidenceEdit(detailEvidenceIndex);', self.source)
        self.assertIn('class="evidence-edit-button contextual-action"', self.source)
        self.assertIn('data-evidence-action="edit"', self.source)


if __name__ == '__main__':
    unittest.main()
