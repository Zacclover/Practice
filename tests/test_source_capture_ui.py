import re
import unittest
from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "index.html").read_text(encoding="utf-8")


class SourceCaptureUiContractTests(unittest.TestCase):
    def test_every_competitor_card_has_a_non_overlapping_source_management_entry(self):
        self.assertIn('class="source-management-trigger secondary"', SOURCE)
        self.assertIn('data-source-competitor-id="${escapeHtml(item.id)}"', SOURCE)
        self.assertIn('>\n                    来源管理\n', SOURCE)
        self.assertRegex(
            SOURCE,
            r"\.competitor-source-management\s*\{[^}]*border-top:\s*1px solid var\(--line-subtle\)",
        )

    def test_source_dialog_limits_type_frequency_and_public_https_url(self):
        self.assertIn('id="sourceManagementDialog"', SOURCE)
        self.assertIn('id="sourceForm"', SOURCE)
        for value in [
            "product", "changelog", "help", "pricing", "blog", "release-notes"
        ]:
            self.assertIn(f'<option value="{value}">', SOURCE)
        self.assertIn('id="sourceFrequency"', SOURCE)
        self.assertIn('function normalizePublicHttpsSourceUrl(value = \'\')', SOURCE)
        self.assertIn("parsedUrl.protocol !== 'https:'", SOURCE)
        self.assertIn("isPrivateSourceHostname(parsedUrl.hostname)", SOURCE)

    def test_sources_keep_local_fallback_and_report_successful_cloud_sync_honestly(self):
        self.assertIn("const sourceCaptureStorageKey =\n      'competitor-insights-source-capture-v1';", SOURCE)
        self.assertIn('本机保存，尚未同步', SOURCE)
        self.assertIn('登录 GitHub 后将通过受 RLS 保护的云端接口同步来源与候选。', SOURCE)
        self.assertIn('云端已同步', SOURCE)
        self.assertNotIn("SUPABASE_SERVICE_ROLE_KEY", SOURCE)

    def test_review_queue_exposes_pending_metadata_and_human_preparation_action(self):
        self.assertIn('id="reviewQueueButton"', SOURCE)
        self.assertIn('id="reviewQueueDialog"', SOURCE)
        self.assertIn('data-prepare-candidate-id=', SOURCE)
        for label in ["候选标题", "来源竞品", "发现时间", "公开来源"]:
            self.assertIn(label, SOURCE)
        self.assertIn('采纳为证据', SOURCE)
        self.assertIn('仅准备证据草稿，不会自动写入证据或横向对比。', SOURCE)

    def test_preparation_never_writes_evidence_or_matrix(self):
        function = re.search(
            r"function prepareCandidateAsEvidence\(candidateId\) \{(?P<body>.*?)\n    \}",
            SOURCE,
            re.S,
        )
        self.assertIsNotNone(function)
        body = function.group("body")
        self.assertIn("openEvidenceDialog", body)
        self.assertIn("sourceUrl", body)
        self.assertNotIn("evidenceItems.push", body)
        self.assertNotIn("comparisonData", body)
        self.assertNotIn("persistEvidence", body)


if __name__ == "__main__":
    unittest.main()
