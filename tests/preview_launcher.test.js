const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const previewPath = path.resolve(__dirname, '..', 'preview.html');
assert.equal(fs.existsSync(previewPath), true, 'preview.html 应存在');
const preview = fs.readFileSync(previewPath, 'utf8');

// ==============================
// 独立预览必须提供可发现的示例数据控制
// ==============================
assert.match(preview, /id="clearPreviewDataButton"/);
assert.match(preview, /id="restorePreviewDataButton"/);
assert.match(preview, /id="previewFrame"/);
assert.match(preview, /competitor-insights-preview-seed-state/);
assert.match(preview, /localStorage\.getItem\(previewStateKey\)\s*!==\s*'cleared'/);

// ==============================
// 清空操作只影响预览域，并刷新嵌入的候选页面
// ==============================
assert.match(preview, /localStorage\.setItem\(\s*workspaceStorageKey,\s*JSON\.stringify\(emptyWorkspace\)\s*\)/s);
assert.match(preview, /legacyStorageKeys\.forEach\(key\s*=>\s*localStorage\.removeItem\(key\)\)/);
assert.match(preview, /previewFrame\.contentWindow\.location\.reload\(\)/);

console.log('preview launcher contract: ok');
