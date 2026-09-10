const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

test('busy turns drain into one later request, fillers preserve results, stop rejects stale responses', async () => {
  const nodes = new Map(), timers = new Map(), requests = [];
  let timerId = 0;
  const element = () => ({ children: [], value: '', textContent: '', classList: { toggle() {}, remove() {} },
    prepend(el) { this.children.unshift(el); }, set innerHTML(value) { this.children = []; } });
  const context = vm.createContext({
    document: { getElementById(id) { if (!nodes.has(id)) nodes.set(id, element()); return nodes.get(id); }, createElement: element },
    window: { addEventListener() {} }, navigator: {}, performance: { now: () => 1000 }, AbortSignal,
    setTimeout(fn) { timers.set(++timerId, fn); return timerId; }, clearTimeout(id) { timers.delete(id); },
    fetch(url, options) { return new Promise(resolve => requests.push({ body: JSON.parse(options.body), resolve })); },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8'), context);
  context.document.getElementById('nextEn');
  const turn = text => context.onMessage({ type: 'Turn', end_of_turn: true, transcript: text });
  const result = { summary_ja: '確認', unconfirmed: [], next_line_en: 'Which scope?', next_line_ja: '範囲は？', evidence_ids: ['u1'], commits_to_something: false };
  const answer = async index => {
    requests[index].resolve({ ok: true, json: async () => result });
    await new Promise(resolve => setImmediate(resolve));
  };
  turn('For staging');
  assert.equal(requests.length, 1);
  assert.equal(requests[0].body.utterances.length, 1); // the first turn goes out immediately, nothing waits for it
  turn('by Friday.'); turn('Production next week?');
  assert.equal(requests.length, 1); // still in flight: later turns queue behind it rather than racing it
  await answer(0);
  assert.equal(requests.length, 2);
  assert.equal(requests[1].body.utterances.length, 3); // and arrive together as context for one request
  assert.equal(nodes.get('nextEn').textContent, ''); // superseded response never rendered
  turn('Right.'); await answer(1);
  assert.equal(nodes.get('nextEn').textContent, 'Which scope?');
  turn('Production?');
  assert.equal(requests.length, 3); // meaningful two-word or one-word turns are not discarded
  context.stop(); nodes.get('nextEn').textContent = 'stopped';
  await answer(2);
  assert.equal(nodes.get('nextEn').textContent, 'stopped');
});
