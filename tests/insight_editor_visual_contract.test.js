const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

test('insight editor presents a clear industrial hierarchy and derived reference tags', () => {
  assert.match(html, /class="insight-dialog-heading"/);
  assert.match(html, /class="insight-dialog-kicker">INSIGHT BUILDER \/ 01—05/);
  assert.match(html, /\.insight-dialog-heading\s*\{[\s\S]*?border-bottom:\s*2px solid var\(--line-strong\);/);
  assert.match(html, /\.insight-form-chain label\s*\{[\s\S]*?border-top:\s*2px solid var\(--line-strong\);/);
  assert.match(html, /\.insight-derived-fieldset \.insight-reference-options\s*\{[\s\S]*?flex-wrap:\s*wrap;/);
  assert.match(html, /competitors\.filter\(item => derivedIds\.competitorIds\.has\(item\.id\)\)/);
  assert.match(html, /color:\s*var\(--white\) !important;[\s\S]*?border:\s*0 !important;/);
  assert.match(html, /comparisonData\.dimensions\.filter\(item => derivedIds\.dimensionIds\.has\(item\.id\)\)/);
  assert.match(html, /\.insight-association,\s*\.insight-derived-fieldset \.insight-reference-options label\s*\{[\s\S]*?color:\s*var\(--white\);[\s\S]*?background:\s*var\(--orange\);[\s\S]*?clip-path:\s*polygon\(6px 0/);
});
