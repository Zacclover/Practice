import json
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "workers" / "source-capture.mjs"


class SourceCaptureWorkerTests(unittest.TestCase):
    def run_module(self, expression):
        script = textwrap.dedent(
            f"""
            const module = await import({json.dumps(WORKER.as_uri())});
            const result = await ({expression})(module);
            console.log(JSON.stringify(result));
            """
        )
        completed = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(completed.stdout)

    def test_only_safe_public_https_urls_are_accepted_for_capture(self):
        result = self.run_module(
            "(module) => ["
            "module.isSafePublicSourceUrl('https://www.notion.so/releases'), "
            "module.isSafePublicSourceUrl('http://www.notion.so/releases'), "
            "module.isSafePublicSourceUrl('https://localhost/private'), "
            "module.isSafePublicSourceUrl('https://127.0.0.1/private'), "
            "module.isSafePublicSourceUrl('https://user@www.notion.so/private')"
            "]"
        )
        self.assertEqual(result, [True, False, False, False, False])

    def test_ipv6_and_special_use_ip_literals_are_rejected_for_sources_and_images(self):
        result = self.run_module(
            "(module) => ["
            "'https://[::1]/', 'https://[::]/', 'https://[fd00::1]/', "
            "'https://[fe80::1]/', 'https://[ff02::1]/', 'https://[::ffff:127.0.0.1]/', "
            "'https://[2001:4860:4860::8888]/'"
            "].map(module.isSafePublicSourceUrl)"
        )
        self.assertEqual(result, [False, False, False, False, False, False, False])

    def test_equivalent_text_has_one_fingerprint_and_changed_text_generates_review_candidate(self):
        result = self.run_module(
            "async (module) => { "
            "const first = await module.createSnapshot('  Update   shipped today.  '); "
            "const same = await module.createSnapshot('Update shipped today.'); "
            "const changed = await module.createSnapshot('Update shipped tomorrow.'); "
            "return {sameHash: first.contentHash === same.contentHash, "
            "sameCandidate: module.shouldQueueCandidate(first.contentHash, same.contentHash), "
            "changedCandidate: module.shouldQueueCandidate(first.contentHash, changed.contentHash), "
            "text: first.extractedText};"
            "}"
        )
        self.assertTrue(result["sameHash"])
        self.assertFalse(result["sameCandidate"])
        self.assertTrue(result["changedCandidate"])
        self.assertEqual(result["text"], "Update shipped today.")

    def test_same_origin_first_level_subpages_are_safely_discovered_and_capped(self):
        result = self.run_module(
            "(module) => module.discoverFirstLevelSameOriginHtmlLinks("
            "'<a href=\"/releases/a#overview\">A</a><a href=\"https://example.com/releases/b\">B</a><a href=\"https://outside.test/x\">X</a><a href=\"http://example.com/no\">No</a><a href=\"/releases/a\">Duplicate</a>', "
            "'https://example.com/releases')"
        )
        self.assertEqual(result, ["https://example.com/releases/a", "https://example.com/releases/b"])

    def test_subpage_discovery_has_a_hard_limit_of_thirty(self):
        result = self.run_module(
            "(module) => module.discoverFirstLevelSameOriginHtmlLinks(Array.from({length: 35}, (_, i) => `<a href=\"/updates/${i}\">${i}</a>`).join(''), 'https://example.com/releases').length"
        )
        self.assertEqual(result, 30)

    def test_worker_batches_snapshot_and_image_writes_to_stay_within_subrequest_budget(self):
        source = WORKER.read_text(encoding="utf-8")
        self.assertIn("async function saveRawSnapshots", source)
        self.assertIn("JSON.stringify(snapshotRows)", source)
        self.assertIn("JSON.stringify(imageRows)", source)
        self.assertNotIn("async function saveRawSnapshot(env", source)

    def test_worker_writes_review_pipeline_only_never_evidence_or_matrix_entities(self):
        source = WORKER.read_text(encoding="utf-8")
        self.assertIn("export default", source)
        self.assertIn("scheduled", source)
        self.assertIn("source_capture_candidates", source)
        self.assertIn("source_capture_snapshots", source)
        self.assertNotIn("/rest/v1/evidence", source)
        self.assertNotIn("/rest/v1/matrix_cells", source)
        self.assertNotIn("/rest/v1/insights", source)

    def test_public_image_urls_are_resolved_deduplicated_and_filtered(self):
        result = self.run_module(
            "(module) => module.extractPublicImageUrls("
            "'<img src=\"/shot.png\" alt=\"界面\"><img src=\"/shot.png\"><img src=\"http://bad.test/a.png\"><img src=\"https://127.0.0.1/a.png\">', "
            "'https://example.com/releases')"
        )
        self.assertEqual(result, [{"url": "https://example.com/shot.png", "alt": "界面"}])


if __name__ == "__main__":
    unittest.main()
