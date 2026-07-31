import unittest
from pathlib import Path


INDEX_PATH = Path(__file__).resolve().parents[1] / "index.html"


class CompetitorCardLayoutContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = INDEX_PATH.read_text(encoding="utf-8")

    def test_cards_use_a_compact_width_without_vertical_content_clipping(self):
        self.assertIn('flex: 0 0 400px;', self.source)
        self.assertIn('width: 400px;', self.source)
        self.assertNotIn('height: 480px;', self.source)
        self.assertIn('height: auto;\n      padding: 22px;\n      overflow: visible;', self.source)

    def test_competitor_track_keeps_cards_naturally_sized_by_content(self):
        self.assertIn('align-items: flex-start;', self.source)

    def test_dimension_column_uses_a_compact_fixed_width(self):
        self.assertIn('min-width: 150px !important;', self.source)
        self.assertIn('max-width: 150px;', self.source)

    def test_dimension_cells_preserve_sticky_position_against_the_generic_td_rule(self):
        self.assertIn('.comparison-table td.dimension-column {\n      position: sticky;', self.source)
        self.assertIn('left: 0;', self.source)
        self.assertIn('z-index: 2;', self.source)


if __name__ == '__main__':
    unittest.main()
