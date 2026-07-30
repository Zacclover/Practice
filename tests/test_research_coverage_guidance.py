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

    def test_uncovered_matrix_cells_offer_a_specific_evidence_capture_entry(self):
        self.assertIn('class="matrix-coverage-gap"', self.source)
        self.assertIn('data-coverage-gap-competitor-id=', self.source)
        self.assertIn('data-coverage-gap-dimension-id=', self.source)
        self.assertIn('补充证据', self.source)

    def test_gap_entry_prefills_the_competitor_and_dimension_in_the_evidence_form(self):
        self.assertRegex(
            self.source,
            r'function openEvidenceDialog\(competitorId, dimensionId = null\)',
        )
        self.assertIn('selectedEvidenceDimensionIds = new Set([dimensionId]);', self.source)
        self.assertIn("button[data-coverage-gap-competitor-id]", self.source)
        self.assertIn('openEvidenceDialog(\n          gapButton.dataset.coverageGapCompetitorId,\n          gapButton.dataset.coverageGapDimensionId\n        );', self.source)

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


if __name__ == '__main__':
    unittest.main()
