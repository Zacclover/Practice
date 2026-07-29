const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');

// ==============================
// 从正式单文件应用提取真实函数，避免复制一份测试实现
// ==============================
function extractFunction(name) {
  const start = html.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `正式应用缺少 ${name}()`);
  const signatureEnd = html.indexOf(') {', start);
  assert.notEqual(signatureEnd, -1, `${name}() 签名不完整`);
  const bodyStart = signatureEnd + 2;
  let depth = 0;
  let quote = null;
  let escaped = false;

  for (let index = bodyStart; index < html.length; index += 1) {
    const character = html[index];
    if (quote) {
      if (escaped) {
        escaped = false;
      } else if (character === '\\') {
        escaped = true;
      } else if (character === quote) {
        quote = null;
      }
      continue;
    }
    if (character === '"' || character === "'" || character === '`') {
      quote = character;
      continue;
    }
    if (character === '{') depth += 1;
    if (character === '}') {
      depth -= 1;
      if (depth === 0) return html.slice(start, index + 1);
    }
  }
  throw new Error(`${name}() 函数边界不完整`);
}

function createRuntime(evidenceItems) {
  const context = vm.createContext({
    Array,
    Date,
    Set,
    String,
    evidenceItems,
    createId: () => 'generated-id',
    createDefaultComparisonData: () => ({
      dimensions: [],
      values: {}
    }),
    normalizeEvidenceItem: item => ({
      ...item,
      dimensionIds: Array.isArray(item.dimensionIds)
        ? item.dimensionIds
        : []
    }),
    normalizeWebsiteUrl: value => value
  });
  vm.runInContext(extractFunction('getInsightDerivedReferenceIds'), context);
  vm.runInContext(extractFunction('synchronizeInsightReferences'), context);
  vm.runInContext(extractFunction('normalizeInsightItem'), context);
  vm.runInContext(extractFunction('normalizeWorkspaceTab'), context);
  return context;
}

const evidence = [
  {
    id: 'e-a',
    competitorId: 'competitor-a',
    dimensionIds: ['dimension-a', 'dimension-shared']
  },
  {
    id: 'e-b',
    competitorId: 'competitor-b',
    dimensionIds: ['dimension-b', 'dimension-shared']
  }
];

// ==============================
// 导入、迁移和加载必须把证据作为唯一关联真源
// ==============================
test('normalizeInsightItem ignores conflicting imported derived ids', () => {
  const runtime = createRuntime(evidence);
  const normalized = runtime.normalizeInsightItem({
    id: 'insight-1',
    title: '证据唯一真源',
    evidenceIds: ['e-a', 'missing', 'e-a'],
    competitorIds: ['competitor-b'],
    dimensionIds: ['dimension-b']
  }, {
    competitorIds: new Set(['competitor-a', 'competitor-b']),
    dimensionIds: new Set([
      'dimension-a',
      'dimension-b',
      'dimension-shared'
    ]),
    evidenceIds: new Set(['e-a', 'e-b']),
    evidenceItems: evidence
  });

  assert.deepEqual([...normalized.evidenceIds], ['e-a']);
  assert.deepEqual([...normalized.competitorIds], ['competitor-a']);
  assert.deepEqual(
    [...normalized.dimensionIds],
    ['dimension-a', 'dimension-shared']
  );
});

// ==============================
// 完整 Tab 归一化是加载、迁移和导入共同经过的数据边界
// ==============================
test('normalizeWorkspaceTab rederives imported insight references', () => {
  const runtime = createRuntime(evidence);
  const tab = runtime.normalizeWorkspaceTab({
    id: 'tab-1',
    name: '导入空间',
    competitors: [
      { id: 'competitor-a', name: 'A' },
      { id: 'competitor-b', name: 'B' }
    ],
    evidenceItems: evidence,
    comparisonData: {
      dimensions: [
        { id: 'dimension-a', name: 'DA' },
        { id: 'dimension-b', name: 'DB' },
        { id: 'dimension-shared', name: 'DS' }
      ],
      values: {}
    },
    insights: [{
      id: 'insight-imported',
      evidenceIds: ['e-a'],
      competitorIds: ['competitor-b'],
      dimensionIds: ['dimension-b']
    }]
  }, 0);

  assert.deepEqual(
    [...tab.insights[0].competitorIds],
    ['competitor-a']
  );
  assert.deepEqual(
    [...tab.insights[0].dimensionIds],
    ['dimension-a', 'dimension-shared']
  );
});

// ==============================
// 证据并集、去重、编辑和删除后的重新派生
// ==============================
test('synchronizeInsightReferences recomputes unions and clears stale ids', () => {
  const runtime = createRuntime(evidence);
  const [synchronized] = runtime.synchronizeInsightReferences([
    {
      id: 'insight-1',
      evidenceIds: ['e-a', 'e-b', 'e-a', 'missing'],
      competitorIds: ['stale-competitor'],
      dimensionIds: ['stale-dimension']
    }
  ], evidence);

  assert.deepEqual([...synchronized.evidenceIds], ['e-a', 'e-b']);
  assert.deepEqual(
    [...synchronized.competitorIds],
    ['competitor-a', 'competitor-b']
  );
  assert.deepEqual(
    [...synchronized.dimensionIds],
    ['dimension-a', 'dimension-shared', 'dimension-b']
  );

  const [afterDelete] = runtime.synchronizeInsightReferences(
    [synchronized],
    []
  );
  assert.deepEqual([...afterDelete.evidenceIds], []);
  assert.deepEqual([...afterDelete.competitorIds], []);
  assert.deepEqual([...afterDelete.dimensionIds], []);

  const editedEvidence = [{
    ...evidence[0],
    dimensionIds: ['dimension-edited']
  }];
  const [afterEdit] = runtime.synchronizeInsightReferences(
    [{ ...synchronized, evidenceIds: ['e-a'] }],
    editedEvidence
  );
  assert.deepEqual([...afterEdit.dimensionIds], ['dimension-edited']);
});

// ==============================
// 最终状态写入和证据变更路径必须接入同一同步函数
// ==============================
test('evidence mutation and persistence paths enforce the invariant', () => {
  assert.match(
    html,
    /evidenceItems\[editingEvidenceIndex\]\s*=\s*evidence;[\s\S]*?insights\s*=\s*synchronizeInsightReferences\(\s*insights,\s*evidenceItems\s*\);[\s\S]*?persistEvidence\(\);/
  );
  assert.match(
    html,
    /evidenceItems\.splice\(evidenceIndex,\s*1\);[\s\S]*?insights\s*=\s*synchronizeInsightReferences\(\s*insights,\s*evidenceItems\s*\);[\s\S]*?persistEvidence\(\);/
  );
  assert.match(
    html,
    /function persistWorkspaceState\(\)\s*\{[\s\S]*?insights\s*=\s*synchronizeInsightReferences\(\s*insights,\s*evidenceItems\s*\);[\s\S]*?activeWorkspaceTab\.insights\s*=\s*insights;/
  );
});

// ==============================
// 原证据 Icon 的两层显示与交互契约
// ==============================
test('evidence view icons are contextual, aligned and keyboard reachable', () => {
  assert.match(
    html,
    /\.insight-evidence-view\s*\{[^}]*width:\s*40px;[^}]*height:\s*40px;[^}]*opacity:\s*0;[^}]*pointer-events:\s*none;[^}]*transform:\s*translateY\(-50%\);/s
  );
  assert.match(
    html,
    /\.insight-evidence-option:hover\s+\.insight-evidence-view,\s*\.insight-evidence-option:focus-within\s+\.insight-evidence-view\s*\{[^}]*opacity:\s*1;[^}]*pointer-events:\s*auto;/s
  );
  assert.match(
    html,
    /\.insight-evidence-view:hover,\s*\.insight-evidence-view:focus-visible\s*\{[^}]*color:\s*var\(--white\);[^}]*background:\s*var\(--black\);[^}]*transform:\s*translateY\(-50%\);/s
  );
  const insightCss = html.slice(
    html.indexOf('/* 洞察关联以证据为主选择'),
    html.indexOf('.insight-derived-fieldset')
  );
  assert.doesNotMatch(
    insightCss,
    /@media\s*\(hover:\s*none\)[\s\S]*?\.insight-evidence-view\s*\{[^}]*opacity:\s*1/
  );
});
