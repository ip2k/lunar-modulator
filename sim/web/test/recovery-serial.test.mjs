// SPDX-License-Identifier: MIT
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { TransformStream } from 'node:stream/web';
import { openSerialTransport, serialSupported, TRANSPORTER_USB } from '../www/recovery-serial.js';
import { TransporterLink, RecoverySession } from '../www/recovery-transporter.js';

/** A SerialPort-shaped fake answering ping/status like the transporter. */
function fakePort() {
  const rx = new TransformStream(); // device -> host
  const tx = new TransformStream(); // host -> device
  const w = rx.writable.getWriter();
  const log = [];
  (async () => {
    const r = tx.readable.getReader(); let text = '';
    for (;;) {
      const { value, done } = await r.read(); if (done) break;
      text += new TextDecoder().decode(value);
      for (let i = text.indexOf('\n'); i >= 0; i = text.indexOf('\n')) {
        const line = text.slice(0, i); text = text.slice(i + 1); log.push(line);
        if (line === 'ping') await w.write(new TextEncoder().encode('PONG\n'));
        if (line === 'status') await w.write(new TextEncoder().encode('OK uboot=0 v15=0 loader=0 loader_running=0\n'));
      }
    }
  })();
  return { log, opened: null, closed: false, readable: rx.readable, writable: tx.writable,
    async open(o) { this.opened = o; }, async close() { this.closed = true; }, unplug: () => w.close() };
}

test('serial adapter opens at 115200 and carries the protocol', async () => {
  const port = fakePort();
  const link = new TransporterLink(await openSerialTransport(port), { timeoutMs: 500 });
  const session = new RecoverySession(link);
  assert.equal(await session.connect(), true);
  assert.equal((await session.status()).uboot, false);
  assert.deepEqual(port.opened, { baudRate: 115200 });
  assert.deepEqual(port.log, ['ping', 'status']);
  await link.close();
  assert.equal(port.closed, true);
});

test('unplug / reboot closes the link', async () => {
  const port = fakePort();
  const link = new TransporterLink(await openSerialTransport(port), { timeoutMs: 500 });
  const waiting = link.takeLine().catch((e) => e.code);
  await port.unplug();
  assert.equal(await waiting, 'port-closed');
});

test('feature detection and the filter ids', () => {
  assert.equal(serialSupported({ serial: {} }), true);
  assert.equal(serialSupported({}), false);
  assert.deepEqual(TRANSPORTER_USB, { usbVendorId: 0x2e8a, usbProductId: 0x000a });
});
