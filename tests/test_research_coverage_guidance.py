import re
import unittest
from pathlib import Path


INDEX_PATH = Path(__file__).resolve().parents[1] / "index.html"


class ResearchCoverageGuidanceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = INDEX_PATH.read_text(encoding="utf-8")

    def test_matrix_header_has_a_live_research_coverage_summary(self):
        self.assertIn('id="researchCoverageSummary"', self.source)
        self.assertIn('function getResearchCoverage()', self.source)
        self.assertIn('已覆盖 ${coverage.coveredCellCount} / ${coverage.totalCellCount} 个比较点', self.source)

    def test_every_matrix_cell_offers_a_specific_evidence_capture_entry(self):
        self.assertIn('class="matrix-quick-capture"', self.source)
        self.assertIn('data-quick-evidence-competitor-id=', self.source)
        self.assertIn('data-quick-evidence-dimension-id=', self.source)
        self.assertIn('快速记录', self.source)

    def test_gap_entry_prefills_the_competitor_and_dimension_for_capture(self):
        self.assertRegex(
            self.source,
            r'function openQuickEvidenceDialog\(competitorId, dimensionId = null\)',
        )
        self.assertIn('selectedQuickEvidenceDimensionIds = dimensionId', self.source)
        self.assertIn("button[data-quick-evidence-competitor-id]", self.source)
        self.assertIn('openQuickEvidenceDialog(\n          quickCaptureButton.dataset.quickEvidenceCompetitorId,\n          quickCaptureButton.dataset.quickEvidenceDimensionId\n        );', self.source)

    def test_coverage_uses_evidence_associations_not_manual_matrix_notes(self):
        coverage_function = re.search(
            r'function getResearchCoverage\(\) \{(?P<body>.*?)\n\s*\}',
            self.source,
            re.S,
        )
        self.assertIsNotNone(coverage_function)
        assert coverage_function is not None
        self.assertIn('evidence.dimensionIds.includes(dimension.id)', coverage_function.group('body'))
        self.assertNotIn('comparisonData.values', coverage_function.group('body'))

    def test_coverage_components_follow_the_industrial_design_tokens(self):
        summary_rule = re.search(
            r'\.research-coverage-summary\s*\{(?P<body>.*?)\n\s*\}',
            self.source,
            re.S,
        )
        quick_capture_rule = re.search(
            r'\.matrix-quick-capture\s*\{(?P<body>.*?)\n\s*\}',
            self.source,
            re.S,
        )
        self.assertIsNotNone(summary_rule)
        self.assertIsNotNone(quick_capture_rule)
        assert summary_rule is not None and quick_capture_rule is not None
        self.assertIn('var(--gray-100)', summary_rule.group('body'))
        self.assertIn('var(--orange)', summary_rule.group('body'))
        self.assertIn('var(--line-medium)', quick_capture_rule.group('body'))
        self.assertIn('border-radius: 0', quick_capture_rule.group('body'))
        self.assertNotRegex(
            summary_rule.group('body') + quick_capture_rule.group('body'),
            r'#[0-9a-fA-F]{3,8}',
        )


if __name__ == '__main__':
    unittest.main()
