import json
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
WORKER = (ROOT / "workers" / "source-capture.mjs").read_text(encoding="utf-8")
MIGRATIONS = "\n".join(
    path.read_text(encoding="utf-8")
    for path in sorted((ROOT / "supabase" / "migrations").glob("*.sql"))
)


class LocalAiEvidenceFlowTests(unittest.TestCase):
    def test_capture_saves_raw_snapshot_without_creating_candidate(self):
        self.assertIn("capture_mode: triggerType", WORKER)
        self.assertIn('summary_status: "pending"', WORKER)
        self.assertIn("Candidate 必须由浏览器本地 AI 总结成功后创建", WORKER)
        self.assertIn("collectDatedUpdateSections", WORKER)
        self.assertNotIn('insertRecord(env, "source_capture_candidates"', WORKER)

    def test_public_html_images_are_normalized_as_snapshot_metadata(self):
        self.assertIn("export function extractPublicImageUrls", WORKER)
        self.assertIn("section.images", WORKER)
        self.assertIn("source_capture_snapshot_images", WORKER)
        self.assertIn("isSafePublicSourceUrl", WORKER)

    def test_review_queue_uses_one_competitor_batch_record_per_capture_source(self):
        self.assertIn("<h3>${escapeHtml(competitor?.name || '已移除竞品')}</h3>", INDEX)
        self.assertIn("来源：${escapeHtml(source?.label || '已移除来源')}", INDEX)
        self.assertIn("data-generate-summary-source-id", INDEX)
        self.assertIn("batchRawItems", INDEX)
        self.assertNotIn("rawItems.map(raw => `<article class=\"review-raw-item\"", INDEX)

    def test_batch_generation_has_visible_processing_states_and_preserves_local_only_boundary(self):
        self.assertIn("检查本机 WebGPU…", INDEX)
        self.assertIn("正在加载本地模型…", INDEX)
        self.assertIn("正在生成英文 JSON（${index + 1}/${rawItems.length}）", INDEX)
        self.assertIn("正在保存待审核证据（${index + 1}/${rawItems.length}）", INDEX)
        self.assertIn("const prefix = cacheHit ? '正在从本机模型缓存加载' : '正在下载本地模型';", INDEX)
        self.assertIn("getLocalModelButtonLabel", INDEX)
        self.assertIn("正在下载本地模型…", INDEX)
        self.assertIn("text-align: right", INDEX)
        self.assertIn("onProgress(progress)", INDEX)
        self.assertNotIn("lastPhase = progress.phase", INDEX)
        self.assertIn("downloadProgress", INDEX)
        self.assertIn("下载进度超过 5 分钟没有增加", INDEX)
        self.assertIn("已用 ${elapsedSec}s", INDEX)
        self.assertIn("local-summary-loader", INDEX)
        self.assertIn("stroke-dasharray=\"25 10\"", INDEX)
        self.assertIn("transform-box: fill-box", INDEX)
        self.assertNotIn("border-right-color: transparent", INDEX)
        self.assertIn("data-generate-summary-source-id", INDEX)

    def test_review_queue_shows_batch_count_and_local_summary_entry(self):
        self.assertIn("待总结证据（${batchRawItems.length}）", INDEX)
        self.assertIn("AI 总结生成证据", INDEX)
        self.assertIn("createCandidatesFromLocalSummary", INDEX)

    def test_local_model_input_is_token_budgeted_and_errors_are_localized(self):
        self.assertIn("truncateLocalEvidenceText", INDEX)
        self.assertIn("maxBudget = 1400", INDEX)
        self.assertIn("Return English JSON only", INDEX)
        self.assertIn("本地模型英文 JSON 未通过长度检查", INDEX)
        self.assertIn("summary.length < 2", INDEX)
        self.assertNotIn("summary.length < 10", INDEX)
        self.assertIn("isValidLocalChineseSummary", INDEX)
        self.assertIn("renderReviewQueue();", INDEX)
        self.assertIn("generate: prompt length", INDEX)
        self.assertIn("原始页面内容过长", INDEX)
        self.assertIn("LOCAL_MODEL_CACHE_NAME", INDEX)
        self.assertIn("fetchWithPersistentCache", INDEX)
        self.assertIn("caches.open(LOCAL_MODEL_CACHE_NAME)", INDEX)
        self.assertIn("navigator.storage?.persist", INDEX)
        self.assertIn("weightCacheHit", INDEX)
        self.assertIn("正在从本机模型缓存加载", INDEX)
        self.assertIn("downloadProgress: progressed && !fromCache", INDEX)
        self.assertIn("fetchArrayBuffer: async url", INDEX)
        self.assertIn("fetchJson: async url", INDEX)
        self.assertIn("本地模型输出未完成", INDEX)
        self.assertIn("maxLength: 400", INDEX)
        self.assertIn("maxTokens: 512", INDEX)

    def test_expired_cloud_session_refreshes_before_capture_or_rpc(self):
        self.assertIn("cloudAuthRefreshTokenKey", INDEX)
        self.assertIn("refreshCloudAccessToken", INDEX)
        self.assertIn("grant_type=refresh_token", INDEX)
        self.assertIn("ensureFreshCloudAccessToken", INDEX)
        self.assertIn("const accessToken = await ensureFreshCloudAccessToken();", INDEX)
        self.assertIn("response.status === 401 || response.status === 403", INDEX)

    def test_browser_local_inference_has_no_remote_fallback(self):
        readiness = re.search(
            r"async function checkLocalEvidenceModelReadiness\([^)]*\) \{(?P<body>.*?)\n    \}",
            INDEX,
            re.S,
        )
        self.assertIsNotNone(readiness)
        self.assertIn("navigator.gpu", readiness.group("body"))
        self.assertIn("requestAdapter", readiness.group("body"))
        inference = re.search(
            r"async function generateLocalEvidenceSummary\([^)]*\) \{(?P<body>.*?)\n    \}",
            INDEX,
            re.S,
        )
        self.assertIsNotNone(inference)
        self.assertIn("BitGPU", INDEX)
        self.assertIn("localEvidenceModelConfig", INDEX)
        self.assertIn("await model.generate", inference.group("body"))
        self.assertNotIn("fetch(", inference.group("body"))
        self.assertNotIn("cloudRestRequest", inference.group("body"))

    def test_bonsai_english_json_is_translated_by_vendored_local_bergamot_before_candidate_write(self):
        self.assertIn("@mkljczk/bergamot-translator", (ROOT / "assets" / "bergamot-translator" / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8"))
        self.assertTrue((ROOT / "assets" / "bergamot-translator" / "translator.js").is_file())
        self.assertTrue((ROOT / "assets" / "bergamot-translator" / "worker" / "translator-worker.js").is_file())
        self.assertTrue((ROOT / "assets" / "bergamot-translator" / "worker" / "bergamot-translator-worker.wasm").is_file())
        self.assertIn("Mozilla Firefox Translations en→zh-Hans", INDEX)
        self.assertIn("42992955", INDEX)
        self.assertIn("CachedBergamotTranslatorBacking", INDEX)
        self.assertIn("loadLocalEvidenceTranslator", INDEX)
        self.assertIn("translateLocalEvidenceSummary", INDEX)
        self.assertIn("正在下载离线翻译模型", INDEX)
        self.assertIn("正在进行本机英译简体中文", INDEX)
        self.assertIn("离线翻译失败", INDEX)
        self.assertIn("LOCAL_TRANSLATION_CACHE_NAME", INDEX)
        self.assertIn("crypto.subtle.digest('SHA-256'", INDEX)
        handler = re.search(
            r"async function createCandidatesFromLocalSummary\([^)]*\) \{(?P<body>.*?)\n    \}",
            INDEX,
            re.S,
        )
        self.assertIsNotNone(handler)
        body = handler.group("body")
        self.assertLess(body.index("translateLocalEvidenceSummary"), body.index("create_local_summary_candidate"))
        self.assertNotIn("translator.create", body[body.index("translateLocalEvidenceSummary"):body.index("create_local_summary_candidate")])

    def test_translation_uses_pinned_firefox_model_and_no_browser_or_cloud_translation_api(self):
        registry = (ROOT / "assets" / "bergamot-translator" / "enzh-registry.json").read_text(encoding="utf-8")
        self.assertIn("TiberiuCristianLeon/Bergamot/resolve/004d535a7a754590888eceec5ac3a9a43ae7d384/base/enzh", registry)
        self.assertIn("targetLanguage: 'zh-Hans'", INDEX)
        self.assertNotIn("chrome.translator", INDEX.lower())
        self.assertNotIn("translation.googleapis.com", INDEX)
        self.assertNotIn("translate.googleapis.com", INDEX)

    def test_bergamot_runtime_request_matches_the_enzh_registry_key(self):
        registry = json.loads((ROOT / "assets" / "bergamot-translator" / "enzh-registry.json").read_text(encoding="utf-8"))
        self.assertIn("enzh", registry)
        runtime_pair = ("enzh"[:2], "enzh"[2:4])
        self.assertEqual(runtime_pair, ("en", "zh"))
        self.assertIn("runtimeTargetLanguage: 'zh'", INDEX)
        self.assertIn("to: localTranslationConfig.runtimeTargetLanguage", INDEX)

    def test_bergamot_gzip_assets_are_verified_then_decompressed_locally_before_wasm(self):
        self.assertIn("decompressLocalTranslationGzip", INDEX)
        self.assertIn("new DecompressionStream('gzip')", INDEX)
        self.assertIn("浏览器不支持本机 gzip 解压", INDEX)
        self.assertIn("decompressLocalTranslationGzip(buffer, url)", INDEX)
        self.assertIn("await sha256Hex(buffer) !== expectedSha256Hash", INDEX)

    def test_local_chinese_validation_requires_chinese_but_allows_mixed_terms(self):
        source_path = json.dumps(str(ROOT / "index.html"))
        script = f"""
import fs from 'node:fs';
const source = fs.readFileSync({source_path}, 'utf8');
function extract(name) {{
  const start = source.indexOf(`function ${{name}}`);
  if (start < 0) throw new Error(`missing function: ${{name}}`);
  const open = source.indexOf('{{', start);
  let depth = 0;
  for (let i = open; i < source.length; i += 1) {{
    if (source[i] === '{{') depth += 1;
    if (source[i] === '}}') {{
      depth -= 1;
      if (depth === 0) return source.slice(start, i + 1);
    }}
  }}
  throw new Error(`unterminated function: ${{name}}`);
}}
const localValidation = new Function([
  extract('isPlaceholderLocalChineseSummary'),
  extract('getLocalChineseSummaryValidationError'),
  'return {{ getLocalChineseSummaryValidationError }};',
].join(String.fromCharCode(10)))();
const valid = localValidation.getLocalChineseSummaryValidationError(
  'Notion AI 新增 sharing 功能',
  'Notion AI 支持团队更快地整理 project updates 与相关上下文。'
);
if (valid) throw new Error(`mixed Chinese content should be accepted: ${{valid}}`);
const shortSummary = localValidation.getLocalChineseSummaryValidationError(
  'Notion 分享更新',
  '支持共享'
);
if (shortSummary) throw new Error(`short Chinese summary should be accepted: ${{shortSummary}}`);
const english = localValidation.getLocalChineseSummaryValidationError(
  'Share context with Custom Agents',
  'This update helps teams share context with agents.'
);
if (english !== '功能主题缺少简体中文') throw new Error(`English title should be rejected: ${{english}}`);
"""
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_schema_removes_cloud_ai_budget_and_links_candidate_images(self):
        self.assertIn("drop function if exists public.reserve_source_capture_ai_budget", MIGRATIONS)
        self.assertIn("drop table if exists public.source_capture_ai_daily_usage", MIGRATIONS)
        self.assertIn("create table public.source_capture_snapshot_images", MIGRATIONS)
        self.assertIn("alter table public.candidate_attachments", MIGRATIONS)
        self.assertIn("source_url, image_url", MIGRATIONS)
        self.assertIn("create function public.create_local_summary_candidate", MIGRATIONS)
        self.assertIn("status text not null default 'pending'", MIGRATIONS)
        self.assertIn("revoke insert, update, delete on table public.source_capture_candidates from authenticated", MIGRATIONS)
        self.assertIn("workspace members read source_capture_candidates", MIGRATIONS)
        self.assertIn("for update", MIGRATIONS)
        self.assertIn("snapshot_already_summarized", MIGRATIONS)
        self.assertIn("summary_status = 'generated'", MIGRATIONS)

    def test_placeholder_summary_values_are_rejected_after_local_translation(self):
        self.assertNotIn('输出示例：{"featureTitle":"中文功能主题"', INDEX)
        self.assertNotIn('严格输出：{"featureTitle":"中文功能主题"', INDEX)
        self.assertIn("isPlaceholderLocalChineseSummary", INDEX)
        self.assertIn("getLocalChineseSummaryValidationError", INDEX)
        self.assertIn("translateLocalEvidenceSummary", INDEX)
        self.assertNotIn("pattern: '^[^A-Za-z]*", INDEX)
        self.assertNotIn("hasUnsupportedLatinInLocalChineseField", INDEX)
        self.assertIn("离线翻译失败：译文未通过质量检查", INDEX)
        self.assertIn("role: 'system'", INDEX)
        self.assertIn("Return concise factual English only", INDEX)
        self.assertIn("thinkBudget: 128", INDEX)
        self.assertIn("temperature: 0.5", INDEX)

    def test_unavailable_model_guidance_does_not_create_candidate(self):
        self.assertIn("请重新加载后重试", INDEX)
        self.assertIn("支持 WebGPU 的设备和浏览器", INDEX)
        handler = re.search(
            r"async function createCandidatesFromLocalSummary\([^)]*\) \{(?P<body>.*?)\n    \}",
            INDEX,
            re.S,
        )
        self.assertIsNotNone(handler)
        self.assertIn("checkLocalEvidenceModelReadiness", handler.group("body"))
        self.assertLess(
            handler.group("body").index("checkLocalEvidenceModelReadiness"),
            handler.group("body").index("create_local_summary_candidate"),
        )


if __name__ == "__main__":
    unittest.main()
