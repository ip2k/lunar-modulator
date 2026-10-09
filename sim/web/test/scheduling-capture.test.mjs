// Scheduling evidence must survive missing Linux files and incomplete CDP.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { resourceSnapshot, startSchedulingCapture } from './scheduling-capture.mjs';

const fixture = () => {
  const out = mkdtempSync(join(tmpdir(), 'lunar-scheduling-'));
  const json = (name) => JSON.parse(readFileSync(join(out, name), 'utf8'));
  return { out, json, clean: () => rmSync(out, { recursive: true, force: true }) };
};
const snapshot = () => ({ utc: 'fixture', files: {} });
class Session extends EventEmitter {
  async send(method) {
    this.calls.push(method);
    if (method === 'Tracing.end') {
      // The final batch arrives during the drain, not during the storm.
      this.emit('Tracing.dataCollected', { value: [{ name: 'SyncReader::Read timed out' }, { name: 'Worker::DoRead' }] });
      if (this.complete) this.emit('Tracing.tracingComplete');
    }
  }
  calls = [];
  complete = true;
  async detach() { this.detached = true; }
}

test('resource snapshots preserve counter units and mark unavailable files', () => {
  const r = resourceSnapshot((path) => {
    if (path.endsWith('cpu.stat')) return 'nr_throttled 7\nthrottled_usec 12345\n';
    if (path === '/proc/stat') return 'cpu 1 2 3 4 5 6 7 8\ncpu0 1 2 3 4 5 6 7 8\nintr 900\n';
    if (path === '/proc/self/status') return 'Name: private\nCpus_allowed_list:\t0-3\n';
    const error = new Error('absent'); error.code = 'ENOENT'; throw error;
  });
  assert.equal(r.files['/sys/fs/cgroup/cpu.stat'].text, 'nr_throttled 7\nthrottled_usec 12345');
  assert.deepEqual(r.files['/proc/pressure/cpu'], { text: null, error: 'ENOENT' });
  assert.equal(r.files['/proc/stat'].text, 'cpu 1 2 3 4 5 6 7 8\ncpu0 1 2 3 4 5 6 7 8');
  assert.equal(r.files['/proc/self/status'].text, 'Cpus_allowed_list:\t0-3');
});

test('browser-wide trace drains last batch and labels bounded truncation', async () => {
  const f = fixture(), session = new Session();
  try {
    let browserSessions = 0;
    const browser = { newBrowserCDPSession: async () => { browserSessions++; return session; } };
    const c = await startSchedulingCapture(browser, f.out, { trace: true, snapshot, maxEvents: 1 });
    assert.equal(f.json('editor-scheduling.json').samples.length, 1);
    const r = await c.finish();
    assert.equal(browserSessions, 1);
    assert.equal(r.trace_complete, true);
    assert.equal(r.trace_events_saved, 1);
    assert.equal(r.trace_events_dropped, 1);
    assert.equal(r.samples.length, 2);
    assert.equal(f.json('editor-audio-trace.json').traceEvents[0].name, 'SyncReader::Read timed out');
    assert.equal(session.detached, true);
  } finally { f.clean(); }
});

test('missing trace completion saves partial evidence instead of hanging', async () => {
  const f = fixture(), session = new Session(); session.complete = false;
  try {
    const c = await startSchedulingCapture({ newBrowserCDPSession: async () => session }, f.out,
      { trace: true, snapshot, timeoutMs: 10 });
    const r = await c.finish();
    assert.equal(r.trace_complete, false);
    assert.match(r.errors.join(), /timed out/);
    assert.equal(f.json('editor-audio-trace.json').traceEvents.length, 2);
  } finally { f.clean(); }
});

test('unsupported CDP retains resource evidence and records the failure', async () => {
  const f = fixture();
  try {
    const c = await startSchedulingCapture({ newBrowserCDPSession: async () => { throw new Error('unsupported'); } },
      f.out, { trace: true, snapshot });
    const r = await c.finish();
    assert.equal(r.trace_started, false);
    assert.match(r.errors.join(), /unsupported/);
    assert.equal(f.json('editor-scheduling.json').samples.length, 2);
    assert.deepEqual(f.json('editor-audio-trace.json').traceEvents, []);
  } finally { f.clean(); }
});
