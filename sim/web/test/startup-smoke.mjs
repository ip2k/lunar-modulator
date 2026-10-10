// Actual browser startup/restart regression. Uses the shipped page and Wasm;
// observers record initialization state and destination connection order.
import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { serve } from './serve.mjs';
import { launch } from './launch.mjs';
const [www, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const { server, url } = await serve(www, 8767);
const { browser, name } = await launch();
const page = await browser.newPage();
const report = { browser: name, pass: false, errors: [], starts: [] };
try {
  await page.addInitScript(() => {
    window.__startupNodes = [];
    const Original = window.AudioWorkletNode;
    window.AudioWorkletNode = class extends Original {
      constructor(...args) {
        super(...args);
        this.probe = { ready: false, created_state: args[0].state, created_time: args[0].currentTime, connections: [] };
        const ctx = args[0];
        window.__startupNodes.push(this.probe);
        this.port.addEventListener('message', ({ data }) => { if (data.type === 'ready') {
          this.probe.ready = true; this.probe.ready_state = ctx.state; this.probe.ready_time = ctx.currentTime;
        } });
        this.port.start();
      }
      connect(...args) {
        this.probe.connections.push({ destination: args[0].constructor.name, ready: this.probe.ready });
        return super.connect(...args);
      }
    };
  });
  page.on('pageerror', (e) => report.errors.push(e.message));
  await page.goto(url);
  for (let attempt = 0; attempt < 2; ++attempt) {
    const before = await page.evaluate(() => window.fm1?.screens ?? 0);
    await page.click('#power-on');
    await page.waitForFunction((before) => window.fm1?.ctx && window.fm1.screens > before, before, { timeout: 20000 });
    const first = await page.evaluate(() => ({ screens: window.fm1.screens, audio_seconds: window.fm1.ctx.currentTime }));
    await page.waitForTimeout(150);
    const row = await page.evaluate(() => ({ screens: window.fm1.screens, audio_seconds: window.fm1.ctx.currentTime,
      state: window.fm1.ctx.state, rate: window.fm1.ctx.sampleRate, node: window.__startupNodes.at(-1) }));
    report.starts.push(row);
    assert.equal(row.state, 'running');
    assert.ok(row.screens > first.screens && row.audio_seconds > first.audio_seconds);
    assert.equal(row.node.ready, true);
    assert.equal(row.node.created_state, 'suspended');
    assert.equal(row.node.ready_state, 'suspended');
    assert.equal(row.node.created_time, row.node.ready_time);
    assert.equal(row.node.connections.length, 2);
    assert.ok(row.node.connections.every((c) => c.ready));
    await page.click('#power-off');
    await page.waitForFunction(() => !window.fm1?.ctx, null, { timeout: 20000 });
  }
  assert.deepEqual(report.errors, []);
  report.pass = true;
} finally {
  writeFileSync(join(out, 'startup-smoke.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report));
  await browser.close(); server.close();
}
