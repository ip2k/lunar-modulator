// SPDX-License-Identifier: GPL-3.0-only
// Fake Web MIDI access for the offline OTA tests: scripted FM-1 stock-updater
// peers (identity reply, 7F upgrade, E0000000/F0000000 finish requests).
import { HS_QUERY, UPGRADE, pack7 } from '../www/third_party/fm1-ota/fm1ota.js';

export const same = (a, b) => Array.from(a).join(',') === Array.from(b).join(',');
export const checksum = (bytes) => (~bytes.reduce((sum, byte) => sum + byte, 0)) & 0xff;

export function identity(text) {
  const name = [...new TextEncoder().encode(text)];
  const decoded = [0, 0x59, 0x11, 27, 0, 0, ...name, ...new Array(27 - name.length).fill(0)];
  decoded.push(checksum(decoded.slice(6)));
  return Uint8Array.from([0xf0, ...pack7(decoded), 0xf7]);
}

export function request(addr, length = 4) {
  const decoded = [0, 0x59, 0x30, 8, 0, 0, 0, addr & 0xff, (addr >>> 8) & 0xff,
    (addr >>> 16) & 0xff, (addr >>> 24) & 0xff, length, 0, 0];
  decoded.push(checksum(decoded.slice(6)));
  return Uint8Array.from([0xf0, ...pack7(decoded), 0xf7]);
}

export class FakeAccess {
  constructor() {
    this.sysexEnabled = true;
    this.inputs = new Map();
    this.outputs = new Map();
    this.listeners = new Set();
    this.sent = [];
    this.opens = 0;
  }
  addEventListener(name, listener) { if (name === 'statechange') this.listeners.add(listener); }
  removeEventListener(name, listener) { if (name === 'statechange') this.listeners.delete(listener); }
  addPair(phase, text, { failFinish = false, noDisconnect = false, stall = false,
    dropMidTransfer = false, name = 'USB Composite Device', id = phase } = {}) {
    const access = this;
    let transferStep = 0;
    const input = { id: `${id}-in`, name, type: 'input',
      state: 'connected', onmidimessage: null,
      async open() { access.opens += 1; }, async close() {} };
    const output = { id: `${id}-out`, name: input.name, type: 'output', state: 'connected',
      async open() { access.opens += 1; }, async close() {},
      send(bytes) {
        access.sent.push({ phase, bytes: Array.from(bytes) });
        if (same(bytes, HS_QUERY)) {
          input.onmidimessage?.({ data: identity(text) });
        } else if (same(bytes, UPGRADE)) {
          transferStep = 1;
          input.onmidimessage?.({ data: request(0) });
        } else if (transferStep === 1 && stall) {
          // The host's first data response arrived; the device then goes silent.
          transferStep = 9;
        } else if (transferStep === 1 && dropMidTransfer) {
          transferStep = 9;
          input.state = 'disconnected';
          output.state = 'disconnected';
          for (const listener of access.listeners) listener({ port: input });
        } else if (transferStep === 1) {
          transferStep = 2;
          input.onmidimessage?.({ data: request(phase === 'running' ? 0xe0000000 : 0xf0000000, 8) });
        } else if (transferStep === 2) {
          transferStep = 3;
          if (failFinish) throw new Error('finish send failed');
          if (!noDisconnect) {
            input.state = 'disconnected';
            output.state = 'disconnected';
            access.inputs.delete(input.id);
            access.outputs.delete(output.id);
            for (const listener of access.listeners) listener({ port: input });
          }
        }
      } };
    this.inputs.set(input.id, input);
    this.outputs.set(output.id, output);
    return { input, output };
  }
}

