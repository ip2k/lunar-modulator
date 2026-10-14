// SPDX-License-Identifier: GPL-3.0-only
// Copyright (C) 2026 Leo Kuroshita (@kurogedelic), Hügelton Instruments
// Copyright (C) 2026 Lunar Modulator contributors
//
// Derived from Felucca web/fm1ota.js at 1727537624390cc3f9c7dff2456b43b3a8edb005.
// Local hardening is identified below. This is protocol/transport support only;
// it is not an installer UI and never requests Web MIDI access.

export const HS_QUERY = Object.freeze([0xF0, 0x00, 0x32, 0x45, 0x00, 0x00, 0x00, 0x40, 0x7F, 0xF7]);
export const UPGRADE = Object.freeze([0xF0, 0x22, 0x24, 0x35, 0x7F, 0xF7]);
export const MAXDATA = 512;
export const DEFAULT_QUEUE_LIMIT = 32;
export const DEFAULT_PACKET_LIMIT = 1024;

const FINISH_VERIFY = 0xE0000000;
const FINISH_WRITE = 0xF0000000;
const defaultClock = {
  now: () => globalThis.performance?.now?.() ?? Date.now(),
  setTimeout: (fn, ms) => globalThis.setTimeout(fn, ms),
  clearTimeout: (id) => globalThis.clearTimeout(id),
  sleep: (ms) => new Promise((resolve) => globalThis.setTimeout(resolve, ms)),
};

function fail(code, message) {
  const error = new Error(message);
  error.code = code;
  return error;
}

export function pack7(data) {
  const out = [];
  let acc = 0;
  let bits = 0;
  for (const byte of data) {
    acc |= (byte & 0xFF) << bits;
    bits += 8;
    while (bits >= 7) {
      out.push(acc & 0x7F);
      acc >>>= 7;
      bits -= 7;
    }
  }
  if (bits) out.push(acc & 0x7F);
  return out;
}

export function unpack7(data) {
  const out = [];
  let acc = 0;
  let bits = 0;
  for (const byte of data) {
    if (!Number.isInteger(byte) || byte < 0 || byte > 0x7F) return null;
    acc |= byte << bits;
    bits += 7;
    while (bits >= 8) {
      out.push(acc & 0xFF);
      acc >>>= 8;
      bits -= 8;
    }
  }
  // A final partial 7-bit group is valid only when it contains no hidden data.
  if (bits && acc !== 0) return null;
  return out;
}

function checksumOk(decoded, start, end, checksumIndex) {
  let sum = 0;
  for (let i = start; i < end; i += 1) sum += decoded[i];
  return ((~sum) & 0xFF) === decoded[checksumIndex];
}

function framedPayload(packet) {
  if (!packet || packet.length < 4 || packet[0] !== 0xF0 || packet.at(-1) !== 0xF7) return null;
  const body = unpack7(Array.from(packet).slice(1, -1));
  return body;
}

// Strict parser: framing, decoded size, type, declared body count, and checksum.
export function parseRequest(packet) {
  const decoded = framedPayload(packet);
  if (!decoded || decoded.length !== 15 || decoded[0] !== 0 || decoded[1] !== 0x59 || decoded[2] !== 0x30) return null;
  const declared = decoded[3] | (decoded[4] << 8) | (decoded[5] << 16);
  if (declared !== 8 || !checksumOk(decoded, 6, 14, 14)) return null;
  return {
    fl: decoded[6],
    addr: (decoded[7] | (decoded[8] << 8) | (decoded[9] << 16) | (decoded[10] << 24)) >>> 0,
    len: decoded[11] | (decoded[12] << 8) | (decoded[13] << 16),
  };
}

export function parseIdentity(packet) {
  const decoded = framedPayload(packet);
  if (!decoded || decoded.length !== 34 || decoded[0] !== 0 || decoded[1] !== 0x59 || decoded[2] !== 0x11) return null;
  const declared = decoded[3] | (decoded[4] << 8) | (decoded[5] << 16);
  if (declared !== 27 || !checksumOk(decoded, 6, 33, 33)) return null;
  const bytes = decoded.slice(6, 33);
  while (bytes.at(-1) === 0) bytes.pop();
  if (bytes.some((byte) => byte < 0x20 || byte > 0x7E)) return null;
  const text = String.fromCharCode(...bytes);
  const match = /^([A-Za-z0-9-]+)_(\d{1,3})$/.exec(text);
  if (!match) return null;
  const version = Number(match[2]);
  return Number.isSafeInteger(version) ? { text, model: match[1], version } : null;
}

export function makeResponse(addr, data, flashType = 0) {
  if (!Number.isInteger(addr) || addr < 0 || addr > 0xFFFFFFFF) throw new RangeError("address must be a u32");
  if (!Number.isInteger(flashType) || flashType < 0 || flashType > 0x7F) throw new RangeError("flash type must be a MIDI byte");
  const bytes = Array.from(data);
  if (bytes.length > MAXDATA) throw new RangeError("response exceeds 512-byte protocol maximum");
  const length = bytes.length;
  const body = [0, 0x59, 0x30, length + 8, 0, 0, flashType,
    addr & 0xFF, (addr >>> 8) & 0xFF, (addr >>> 16) & 0xFF, (addr >>> 24) & 0xFF,
    length & 0xFF, (length >>> 8) & 0xFF, 0, ...bytes];
  let sum = 0;
  for (let i = 6; i < body.length; i += 1) sum += body[i];
  body.push((~sum) & 0xFF);
  return [0xF0, ...pack7(body), 0xF7];
}

// Hardened transport: bounded queue and packet size; one pending reader; close
// wakes readers; overflow is terminal rather than silently dropping requests.
export class Link {
  constructor(input, output, { clock = defaultClock, queueLimit = DEFAULT_QUEUE_LIMIT,
    packetLimit = DEFAULT_PACKET_LIMIT } = {}) {
    if (!input || !output || typeof input.open !== "function" || typeof output.open !== "function" || typeof output.send !== "function") {
      throw new TypeError("explicit MIDI input and output ports are required");
    }
    if (!Number.isInteger(queueLimit) || queueLimit < 1 || !Number.isInteger(packetLimit) || packetLimit < 4) {
      throw new RangeError("invalid MIDI queue limits");
    }
    this.input = input;
    this.output = output;
    this.clock = clock;
    this.queueLimit = queueLimit;
    this.packetLimit = packetLimit;
    this.queue = [];
    this.waiter = null;
    this.failure = null;
    this.closed = false;
    this.onMessage = (event) => this.#receive(event?.data);
    input.onmidimessage = this.onMessage;
  }

  get lost() {
    return this.closed || this.input.state === "disconnected" || this.output.state === "disconnected";
  }

  #receive(data) {
    if (this.closed || !data || data.length < 2 || data[0] !== 0xF0) return;
    if (data.length > this.packetLimit) return this.#fail(fail("packet-limit", "incoming SysEx packet exceeded the configured limit"));
    const packet = Array.from(data);
    if (this.waiter) {
      const waiter = this.waiter;
      this.waiter = null;
      this.clock.clearTimeout(waiter.timer);
      waiter.resolve(packet);
      return;
    }
    if (this.queue.length >= this.queueLimit) return this.#fail(fail("queue-overflow", "incoming MIDI queue overflowed"));
    this.queue.push(packet);
  }

  #fail(error) {
    if (this.failure) return;
    this.failure = error;
    if (this.waiter) {
      const waiter = this.waiter;
      this.waiter = null;
      this.clock.clearTimeout(waiter.timer);
      waiter.reject(error);
    }
  }

  send(bytes) {
    if (this.lost || this.failure) return false;
    try {
      this.output.send(bytes);
      return true;
    } catch {
      return false;
    }
  }

  drain() { this.queue.length = 0; }

  read(timeoutMs) {
    if (!Number.isFinite(timeoutMs) || timeoutMs < 0) return Promise.reject(new RangeError("read timeout must be nonnegative"));
    if (this.failure) return Promise.reject(this.failure);
    if (this.queue.length) return Promise.resolve(this.queue.shift());
    if (this.lost) return Promise.resolve(null);
    if (this.waiter) return Promise.reject(new Error("concurrent Link.read calls are not supported"));
    return new Promise((resolve, reject) => {
      const waiter = { resolve, reject, timer: null };
      waiter.timer = this.clock.setTimeout(() => {
        if (this.waiter === waiter) this.waiter = null;
        resolve(null);
      }, timeoutMs);
      this.waiter = waiter;
    });
  }

  close() {
    if (this.closed) return;
    this.closed = true;
    if (this.input.onmidimessage === this.onMessage) this.input.onmidimessage = null;
    this.queue.length = 0;
    if (this.waiter) {
      const waiter = this.waiter;
      this.waiter = null;
      this.clock.clearTimeout(waiter.timer);
      waiter.resolve(null);
    }
  }
}

export async function handshake(link, { clock = defaultClock, tries = 2, timeoutMs = 1000 } = {}) {
  link.drain();
  for (let attempt = 0; attempt < tries; attempt += 1) {
    if (!link.send(HS_QUERY)) return null;
    const deadline = clock.now() + timeoutMs;
    while (clock.now() < deadline) {
      const packet = await link.read(Math.max(0, deadline - clock.now()));
      if (!packet) break;
      const identity = parseIdentity(packet);
      if (identity) return identity;
    }
  }
  return null;
}

// Transfer loop has both an idle timeout and an absolute cap. Valid traffic
// refreshes only the idle deadline. Finish is successful only after ACK send.
export async function serveRequests(link, image, finishAddr, {
  clock = defaultClock,
  idleTimeoutMs = 8000,
  hardTimeoutMs = 180000,
  responseDelayMs = 10,
  onProgress = null,
} = {}) {
  if (!(image instanceof Uint8Array) || image.length === 0) throw new TypeError("logical image must be a nonempty Uint8Array");
  if (![FINISH_VERIFY, FINISH_WRITE].includes(finishAddr)) throw new RangeError("unknown finish address");
  const startedAt = clock.now();
  let lastValidRequest = startedAt;
  let served = 0;
  for (;;) {
    const hardRemaining = hardTimeoutMs - (clock.now() - startedAt);
    const idleRemaining = idleTimeoutMs - (clock.now() - lastValidRequest);
    const remaining = Math.min(hardRemaining, idleRemaining, 1000);
    if (remaining <= 0) return { served, finished: false, timeout: true };
    const packet = await link.read(remaining);
    if (link.lost) return { served, finished: false, lost: true };
    if (!packet) continue;
    const request = parseRequest(packet);
    if (!request) continue;
    lastValidRequest = clock.now();

    if (request.addr === FINISH_VERIFY || request.addr === FINISH_WRITE) {
      const ack = makeResponse(request.addr, [...new TextEncoder().encode("success"), 0]);
      if (!link.send(ack)) return { served, finished: false, lost: true, sendFailed: true };
      if (request.addr === finishAddr) return { served, finished: true };
      continue;
    }

    if (request.len === 0 || request.len > MAXDATA || request.addr >= image.length || request.addr + request.len > image.length) {
      throw fail("badreq", `bad request ${request.addr.toString(16)}+${request.len}`);
    }
    if (clock.now() - startedAt >= hardTimeoutMs) return { served, finished: false, timeout: true };
    if (responseDelayMs > 0) await clock.sleep(responseDelayMs);
    if (clock.now() - startedAt >= hardTimeoutMs) return { served, finished: false, timeout: true };
    const response = makeResponse(request.addr, image.subarray(request.addr, request.addr + request.len), request.fl);
    if (!link.send(response)) return { served, finished: false, lost: true, sendFailed: true };
    served += 1;
    if (onProgress) onProgress(served, request.addr);
  }
}
