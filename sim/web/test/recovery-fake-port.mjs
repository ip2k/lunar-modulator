// SPDX-License-Identifier: MIT
// Fake FM-1 Transporter data port. Replays the line protocol of
// FM-1-transporter src/transporter_proto.c (a7fb5e8) against a 1 MiB flash
// model, delivering output in arbitrary fragments. No hardware involved.
import { crc32, hex8, FLASH_SIZE, WRITE_MIN, WRITE_END, SECTOR, LOADER_SIZE } from '../www/recovery-transporter.js';

const enc = new TextEncoder();

export class FakeTransporter {
  constructor({ flash, uboot = true, v15 = false, chunk = [65536], faults = {} } = {}) {
    this.flash = flash ? flash.slice() : new Uint8Array(FLASH_SIZE).map((_, i) => (i * 31 + (i >> 8)) & 255);
    this.state = { uboot, v15, loader: false, loaderRunning: false };
    this.chunk = chunk; this.chunkIx = 0;
    this.faults = { ...faults };
    this.received = [];     // every request line, in order
    this.inbuf = new Uint8Array(0);
    this.need = null;       // pending payload { verb, args, len }
    this.loaderBytes = 0;
    this.readCount = 0; this.wsecCount = 0; this.writtenSectors = [];
    this.dataCb = () => {}; this.closeCb = () => {};
    this.closed = false;
    this.pending = Promise.resolve();
  }
  // transport interface
  onData(cb) { this.dataCb = cb; }
  onClose(cb) { this.closeCb = cb; }
  async close() { this.closed = true; this.closeCb(); }
  async write(bytes) {
    if (this.closed) throw new Error('closed');
    const m = new Uint8Array(this.inbuf.length + bytes.length); m.set(this.inbuf); m.set(bytes, this.inbuf.length);
    this.inbuf = m;
    this.#pump();
  }
  // output, fragmented
  #emit(bytes) {
    this.pending = this.pending.then(async () => {
      for (let o = 0; o < bytes.length;) {
        const n = Math.min(this.chunk[this.chunkIx++ % this.chunk.length], bytes.length - o);
        if (!this.closed) this.dataCb(bytes.slice(o, o + n));
        o += n;
        await new Promise((r) => setImmediate(r));
      }
    });
  }
  #line(s) { this.#emit(enc.encode(`${s}\n`)); }
  #pump() {
    for (;;) {
      if (this.need) {
        if (this.inbuf.length < this.need.len) return;
        const payload = this.inbuf.slice(0, this.need.len);
        this.inbuf = this.inbuf.slice(this.need.len);
        const { verb, args } = this.need; this.need = null;
        this.#payload(verb, args, payload);
        continue;
      }
      const i = this.inbuf.indexOf(10);
      if (i < 0) return;
      const line = new TextDecoder().decode(this.inbuf.slice(0, i)).trim();
      this.inbuf = this.inbuf.slice(i + 1);
      this.received.push(line);
      this.#handle(line);
    }
  }
  #handle(line) {
    const a = line.split(/\s+/); const verb = a[0];
    const f = this.faults;
    switch (verb) {
      case 'ping': if (!f.pingSilent) this.#line('PONG'); return;
      case 'status':
        if (f.statusSilent) return;
        this.#line(`OK uboot=${+this.state.uboot} v15=${+this.state.v15} loader=${+this.state.loader} loader_running=${+this.state.loaderRunning}`); return;
      case 'rekey':
        this.#line('OK rekey');
        this.pending = this.pending.then(() => { this.state.uboot = false; this.rekeyed = true; if (f.closeOnRekey !== false) { this.closed = true; this.closeCb(); } });
        return;
      case 'uboot': this.softKeyed = true; this.state.uboot = true; this.#line('OK softkey'); return;
      case 'info':
        if (!this.state.uboot) return this.#line('ERR no-uboot');
        return this.#line(f.infoReply || 'OK key=980F type=3 id=856014');
      case 'read': return this.#read(Number(a[1]), Number(a[2]));
      case 'ldr': { const len = Number(a[2]); this.need = { verb, args: a, len }; return undefined; }
      case 'wsec': this.need = { verb, args: a, len: SECTOR }; return undefined;
      default: return this.#line('ERR unknown');
    }
  }
  #read(addr, len) {
    const f = this.faults;
    if (!this.state.uboot) return this.#line('ERR no-uboot');
    if (!this.state.loader) return this.#line('ERR loader');
    if (addr + len > FLASH_SIZE) return this.#line('ERR range');
    this.readCount += 1;
    if (f.flashChangesAfterReads !== undefined && this.readCount === f.flashChangesAfterReads + 1) this.flash[0x50000] ^= 0xff;
    let data = this.flash.slice(addr, addr + len);
    if (f.corruptReadAt === this.readCount) { data = data.slice(); data[100] ^= 1; this.flash.length; }
    if (f.finalReadCorrupt && this.wsecCount > 0 && this.readCount === f.finalReadCorrupt) { data = data.slice(); data[WRITE_MIN + 5] ^= 1; }
    this.#line(`DATA ${len}`);
    if (f.stallAfter !== undefined) { this.#emit(data.slice(0, f.stallAfter)); return undefined; }
    this.#emit(data);
    if (f.endFail === this.readCount) return this.#line('END FAIL');
    const crc = f.badEndCrc === this.readCount ? 0xdeadbeef : crc32(f.corruptReadAt === this.readCount ? this.flash.slice(addr, addr + len) : data);
    return this.#line(`END ${hex8(crc)}`);
  }
  #payload(verb, a, payload) {
    const f = this.faults;
    if (verb === 'ldr') {
      if (f.ldrReply) return this.#line(f.ldrReply);
      if (hex8(crc32(payload)) !== a[3]) return this.#line(`ERR crc ${hex8(crc32(payload))}`);
      if (this.state.loaderRunning) return this.#line('ERR loader-running');
      this.loaderBytes += payload.length;
      if (this.loaderBytes >= LOADER_SIZE) this.state.loader = true;
      return this.#line('OK');
    }
    // wsec
    this.wsecCount += 1;
    const addr = Number(a[1]);
    if (!this.state.uboot) return this.#line('ERR no-uboot');
    if (hex8(crc32(payload)) !== a[2]) return this.#line(`ERR crc ${hex8(crc32(payload))}`);
    if (addr < WRITE_MIN || addr >= WRITE_END || addr % SECTOR) return this.#line('ERR range');
    if (f.wsecNoReplyAt === this.wsecCount) return undefined;
    if (f.wsecErrAt === this.wsecCount) return this.#line('ERR write');
    if (f.wsecSilentDropAt === this.wsecCount) return this.#line('OK'); // claims OK, writes nothing
    this.flash.set(payload, addr);
    this.writtenSectors.push(addr);
    return this.#line('OK');
  }
}

export const LOADER = (() => { const b = new Uint8Array(LOADER_SIZE); for (let i = 0; i < b.length; i += 1) b[i] = (i * 7 + 3) & 255; return b; })();
