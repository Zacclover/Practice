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
        self.assertIn(
            '已覆盖 ${coverage.coveredCellCount} / ${coverage.totalCellCount} 个比较点',
            self.source,
        )

    def test_coverage_uses_evidence_associations_not_manual_matrix_notes(self):
        coverage_function = re.search(
            r'function getResearchCoverage\(\) \{(?P<body>.*?)\n\s*\}',
            self.source,
            re.S,
        )
        self.assertIsNotNone(coverage_function)
        assert coverage_function is not None
        self.assertIn(
            'evidence.dimensionIds.includes(dimension.id)',
            coverage_function.group('body'),
        )
        self.assertNotIn('comparisonData.values', coverage_function.group('body'))

    def test_coverage_summary_follows_the_industrial_design_tokens(self):
        summary_rule = re.search(
            r'\.research-coverage-summary\s*\{(?P<body>.*?)\n\s*\}',
            self.source,
            re.S,
        )
        self.assertIsNotNone(summary_rule)
        assert summary_rule is not None
        self.assertIn('var(--gray-100)', summary_rule.group('body'))
        self.assertIn('var(--orange)', summary_rule.group('body'))
        self.assertNotRegex(summary_rule.group('body'), r'#[0-9a-fA-F]{3,8}')

    def test_coverage_branch_does_not_include_quick_capture_interactions(self):
        self.assertNotIn('matrix-coverage-gap', self.source)
        self.assertNotIn('data-coverage-gap-competitor-id', self.source)
        self.assertNotIn('data-coverage-gap-dimension-id', self.source)
        self.assertNotIn('coverageGapCompetitorId', self.source)
        self.assertNotIn('coverageGapDimensionId', self.source)
        self.assertIn('function openEvidenceDialog(competitorId)', self.source)


if __name__ == '__main__':
    unittest.main()
