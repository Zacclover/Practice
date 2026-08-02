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

    def test_source_dialog_starts_in_list_mode_and_opens_form_on_demand(self):
        self.assertIn('id="sourceListMode"', SOURCE)
        self.assertIn('id="addSourceButton"', SOURCE)
        self.assertIn('id="sourceForm" hidden', SOURCE)
        self.assertIn('function showSourceListMode()', SOURCE)
        self.assertIn('function showSourceFormMode(source = null)', SOURCE)
        self.assertIn("addSourceButton.addEventListener('click', () => showSourceFormMode())", SOURCE)

    def test_source_create_edit_save_and_cancel_return_to_list_mode(self):
        self.assertIn("if (editButton) { showSourceFormMode(item); return; }", SOURCE)
        self.assertIn('persistSourceCaptureState(); showSourceListMode(); render();', SOURCE)
        self.assertIn("cancelSourceEditButton.addEventListener('click', showSourceListMode)", SOURCE)

    def test_source_actions_are_revealed_on_hover_or_keyboard_focus(self):
        actions_rule = re.search(
            r"\.source-item-actions\s*\{(?P<body>[^}]*)\}", SOURCE
        )
        self.assertIsNotNone(actions_rule)
        assert actions_rule is not None
        self.assertIn("opacity: 0", actions_rule.group("body"))
        self.assertIn("pointer-events: none", actions_rule.group("body"))
        self.assertNotIn("visibility: hidden", actions_rule.group("body"))
        self.assertIn(
            ".source-list-item:hover .source-item-actions,\n"
            "    .source-list-item:focus-within .source-item-actions",
            SOURCE,
        )
        self.assertIn("@media (max-width: 640px)", SOURCE)
        self.assertNotIn("@media (hover: none), (max-width: 640px)", SOURCE)

    def test_manual_capture_icon_has_a_disabled_rotating_loading_state(self):
        self.assertIn('id="icon-capture"', SOURCE)
        self.assertIn('data-capture-source-id="${escapeHtml(item.id)}"', SOURCE)
        self.assertIn('data-tooltip="立即抓取此来源"', SOURCE)
        self.assertIn("classList.add('is-loading')", SOURCE)
        self.assertIn('disabled', SOURCE)
        self.assertIn('@keyframes source-capture-spin', SOURCE)
        self.assertIn('prefers-reduced-motion: reduce', SOURCE)
        self.assertIn("function requestManualSourceCapture(sourceId)", SOURCE)

    def test_source_dialog_reports_capture_state_without_claiming_global_sync(self):
        self.assertIn("const sourceCaptureStorageKey =\n      'competitor-insights-source-capture-v1';", SOURCE)
        notice = re.search(r'<p id="sourceSyncNotice".*?</p>', SOURCE, re.S)
        self.assertIsNotNone(notice)
        self.assertIn('来源采集状态', notice.group(0))
        self.assertNotIn('云端已同步', notice.group(0))
        self.assertNotIn('工作区同步', notice.group(0))
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
