import re
import unittest
from pathlib import Path


INDEX_PATH = Path(__file__).resolve().parents[1] / "index.html"


class SectionHeadingGlyphContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = INDEX_PATH.read_text(encoding="utf-8")

    def test_all_top_level_sections_have_a_decorative_content_glyph(self):
        sections = {
            "竞品档案": "竞品档案图画：轨道上的分层资料卡，复用 Hero 工业几何语言",
            "竞品横向对比": "横向对比图画：圆盘坐标内的对齐矩阵板，复用 Hero 工业几何语言",
            "洞察结论": "洞察结论图画：轨道中的信号路径汇聚为方向板，复用 Hero 工业几何语言",
        }
        for title, description in sections.items():
            with self.subTest(title=title):
                self.assertIn(f"<!-- {description} -->", self.source)
                pattern = (
                    rf'(?s)<!-- {re.escape(description)} -->\s*'
                    r'<span class="section-heading-glyph" aria-hidden="true">\s*'
                    r'<svg viewBox="0 0 60 42" focusable="false">.*?</svg>\s*</span>\s*'
                    rf'<span>{re.escape(title)}</span>'
                )
                self.assertRegex(self.source, pattern)

    def test_glyphs_use_shared_industrial_svg_treatment(self):
        self.assertRegex(
            self.source,
            r'\.section-heading-glyph\s*\{[^}]*width: 60px;[^}]*height: 42px;[^}]*align-self: center;',
        )
        self.assertRegex(
            self.source,
            r'\.section-heading-glyph svg\s*\{[^}]*fill: none;[^}]*stroke: currentColor;[^}]*stroke-width: 1\.35;',
        )
        self.assertIn(".section-heading-glyph .glyph-axis", self.source)
        self.assertIn(".section-heading-glyph .glyph-orbit", self.source)
        self.assertIn(".section-heading-glyph .glyph-panel", self.source)

    def test_numbered_title_pseudo_elements_are_removed(self):
        self.assertNotRegex(self.source, r'content:\s*"0[123]\s*/"')
        self.assertNotIn(".section-title::before", self.source)
        self.assertNotIn(".comparison-header h2::before", self.source)
        self.assertNotIn(".insights-header h2::before", self.source)

    def test_narrow_screen_keeps_the_three_glyphs_consistent(self):
        self.assertRegex(
            self.source,
            r'\.section-heading-glyph\s*\{[^}]*width: 48px;[^}]*height: 34px;[^}]*flex-basis: 48px;',
        )


if __name__ == "__main__":
    unittest.main()
