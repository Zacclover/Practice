const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');

// ==============================
// 确认后的洞察卡片仅展示已填写阶段，并保持编辑操作的可辨识边界
// ==============================
test('saved insight cards omit blank stages and keep the edit control outlined', () => {
  assert.match(
    html,
    /\]\.filter\(\(\[,\s*,\s*content\]\)\s*=>\s*content\.trim\(\)\);/
  );
  assert.match(
    html,
    /<div class="insight-chain" style="--insight-stage-count: \$\{stages\.length\}">/
  );
  assert.match(
    html,
    /\.insight-stage\.is-action\s*\{[^}]*background:\s*var\(--orange\);/s
  );
  assert.doesNotMatch(html, /content\s*\|\|\s*'待补充'/);
  assert.match(
    html,
    /\.insight-card:focus-within \.edit-button\s*\{[^}]*border-color:\s*var\(--line-strong\);/s
  );
});
