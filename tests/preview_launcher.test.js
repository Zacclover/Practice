const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const preview = fs.readFileSync(path.join(root, 'preview.html'), 'utf8');

// ==============================
// “清空示例”属于页面内操作，必须紧邻“添加竞品”
// ==============================
assert.match(
  html,
  /<div class="hero-actions">[\s\S]*id="addButton"[\s\S]*id="clearSampleButton"[\s\S]*<\/div>/
);
assert.match(html, /id="clearSampleButton"[^>]*class="secondary"[^>]*hidden/);
assert.match(html, /#clearSampleButton\[hidden\]\s*\{[^}]*display:\s*none;/s);

// ==============================
// 仅被标记的当前示例空间显示按钮，普通手动空间不能误显示
// ==============================
assert.match(html, /competitor-insights-sample-tabs-v1/);
assert.match(html, /function currentWorkspaceHasSampleData\(\)/);
assert.match(html, /sampleWorkspaceTabIds\.has\(activeWorkspaceTab\.id\)/);
assert.match(html, /clearSampleButton\.hidden\s*=\s*!currentWorkspaceHasSampleData\(\)/);

// ==============================
// 确认后一次性清空当前示例空间，并移除它的示例标记
// ==============================
assert.match(html, /clearSampleButton\.addEventListener\('click'/);
assert.match(html, /window\.confirm\(/);
assert.match(html, /sampleWorkspaceTabIds\.delete\(activeWorkspaceTab\.id\)/);
assert.match(html, /competitors\s*=\s*\[\]/);
assert.match(html, /evidenceItems\s*=\s*\[\]/);
assert.match(html, /comparisonData\s*=\s*\{\s*dimensions:\s*\[\],\s*values:\s*\{\}\s*\}/s);
assert.match(html, /insights\s*=\s*\[\]/);
assert.match(html, /persistWorkspaceState\(\);\s*render\(\);/s);

// ==============================
// 预览仅在当前预览版本第一次打开时播种，并记录唯一示例空间
// ==============================
assert.doesNotMatch(preview, /preview-toolbar|previewFrame|clearPreviewDataButton/);
assert.match(preview, /competitor-insights-preview-fixture-v3-seen/);
assert.match(preview, /if\s*\(!localStorage\.getItem\(previewFixtureSeenKey\)\)/);
assert.match(preview, /competitor-insights-sample-tabs-v1/);
assert.match(preview, /JSON\.stringify\(\['preview-tab'\]\)/);
assert.match(preview, /window\.location\.replace\('\.\/index\.html\?preview=combined-layout-insights'\)/);

console.log('sample workspace control contract: ok');
