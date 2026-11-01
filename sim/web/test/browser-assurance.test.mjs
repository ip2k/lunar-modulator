// Negative witnesses for the browser/native test gates, without building or
// launching a browser. Execute the actual bounded source sections with fake
// inputs; keep these extraction anchors explicit so source moves fail loudly.
// MIT licence, like the rest of this repository.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';
import vm from 'node:vm';

const source = (name) => readFileSync(new URL(name, import.meta.url), 'utf8');
function section(text, start, end) {
  const a = text.indexOf(start), b = text.indexOf(end, a + start.length);
  assert.ok(a >= 0 && b > a, `missing source anchors: ${start} / ${end}`);
  return text.slice(a, b);
}

const audioGate = section(source('edit.mjs'), 'let maxDiff = 0;', 'check(fm1.calls.length');
function audioChecks(wasm, native) {
  const checks = [];
  vm.runInNewContext(audioGate, { audio: [wasm], native: { audio: native }, BLOCK: 1,
    Float32Array, check: (ok, why) => checks.push({ ok, why }) });
  return checks;
}
test('edit PCM gate rejects non-finite samples on either side, including equal infinities', () => {
  for (const [wasm, native] of [[NaN, 0], [0, NaN], [NaN, NaN],
    [Infinity, Infinity], [-Infinity, -Infinity]]) {
    const checks = audioChecks([wasm, 0], [native, 0]);
    assert.ok(checks.some(x => !x.ok), `${wasm}/${native} must fail: ${JSON.stringify(checks)}`);
  }
});
test('edit PCM gate retains its finite one-LSB tolerance', () => {
  assert.ok(audioChecks([0, 1 / 32767], [0, 0]).every(x => x.ok));
  assert.ok(audioChecks([0, 2 / 32767], [0, 0]).some(x => !x.ok));
});

test('missing Limiter Drive row fails the browser report instead of skipping GR', async () => {
  const checks = [];
  const gate = section(source('editor-reach.mjs'), 'report.gr = gr;', '// A per-voice cable:');
  await vm.runInNewContext(`(async () => { ${gate} })()`, {
    report: {}, gr: { error: 'no Drive row', rows: [] },
    check: (name, ok) => checks.push({ name, ok })
  });
  assert.ok(checks.some(x => !x.ok), 'the missing field must fail an assertion');
});

const tlsFunction = section(source('screenshot.mjs'), 'function selfSigned() {', 'async function publishingChecks(');
function tlsFixture(failAt) {
  const removed = [], reads = [], out = '/owned-test-fixture/results', dir = join(out, '.fm1-tls-unique');
  const bytes = { 'key.pem': Buffer.from('synthetic key'), 'cert.pem': Buffer.from('synthetic cert') };
  const fn = vm.runInNewContext(`${tlsFunction}; selfSigned`, {
    join, out, mkdtempSync: (prefix) => {
      assert.equal(prefix, join(out, '.fm1-tls-'), 'TLS fixture must stay under the owned output directory');
      return dir;
    },
    execFileSync: () => { if (failAt === 'openssl') throw new Error('openssl witness'); },
    readFileSync: (path) => {
      reads.push(path);
      if (failAt === 'read') throw new Error('read witness');
      return bytes[path.slice(dir.length + 1)];
    },
    rmSync: (path, options) => removed.push({ path, recursive: options.recursive, force: options.force })
  });
  return { fn, removed, reads, dir, bytes };
}
test('TLS fixture returns bytes then removes only its owned temporary directory', () => {
  const f = tlsFixture();
  const result = f.fn();
  assert.equal(result.key, f.bytes['key.pem']);
  assert.equal(result.cert, f.bytes['cert.pem']);
  assert.equal(f.reads.length, 2);
  assert.deepEqual(f.removed, [{ path: f.dir, recursive: true, force: true }]);
});
test('TLS fixture removes its temporary directory after openssl or read failure', () => {
  for (const failure of ['openssl', 'read']) {
    const f = tlsFixture(failure);
    assert.throws(f.fn, new RegExp(`${failure} witness`));
    assert.deepEqual(f.removed, [{ path: f.dir, recursive: true, force: true }]);
  }
});
