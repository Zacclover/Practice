const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const design = fs.readFileSync(path.join(root, 'DESIGN.md'), 'utf8');

// ==============================
// 竞品档案固定正方形与横向滚动契约
// ==============================
assert.match(html, /\.grid\s*\{[^}]*display:\s*flex;[^}]*overflow-x:\s*auto;/s);
assert.match(html, /\.card\s*\{[^}]*flex:\s*0\s+0\s+480px;[^}]*width:\s*480px;[^}]*height:\s*480px;/s);
assert.match(html, /\.card\s*\{[^}]*box-sizing:\s*border-box;/s);

// ==============================
// 横向对比固定列宽与首列吸附契约
// ==============================
assert.match(html, /\.comparison-table\s*\{[^}]*width:\s*max-content;[^}]*min-width:\s*0;/s);
assert.match(html, /\.comparison-table\s+th,[^\{]*\.comparison-table\s+td\s*\{[^}]*width:\s*280px;[^}]*min-width:\s*280px;[^}]*max-width:\s*280px;/s);
assert.match(html, /\.dimension-column\s*\{[^}]*position:\s*sticky;[^}]*left:\s*0;[^}]*width:\s*160px[^}]*min-width:\s*160px[^}]*max-width:\s*160px/s);
assert.match(html, /\.comparison-table\s+tbody\s+\.dimension-column\s*\{[^}]*background:\s*#efeee9;/s);
assert.match(html, /\.comparison-scroll\s*\{[^}]*max-width:\s*100%;[^}]*overflow-x:\s*auto;/s);

// ==============================
// DESIGN.md 必须记录正式布局规则
// ==============================
assert.match(design, /竞品档案卡片固定为 `480px × 480px`/);
assert.match(design, /对比维度列固定 `160px`/);
assert.match(design, /正文固定列使用暖灰 `#EFEEE9`/);
assert.match(design, /竞品列固定 `280px`/);

console.log('layout contract: ok');
