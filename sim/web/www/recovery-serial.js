// SPDX-License-Identifier: MIT
// Adapts a Web Serial `SerialPort` (or a fake with the same shape) to the
// transport interface used by recovery-transporter.js.
export const TRANSPORTER_USB = Object.freeze({ usbVendorId: 0x2e8a, usbProductId: 0x000a });

export async function openSerialTransport(port, { baudRate = 115200 } = {}) {
  await port.open({ baudRate });
  const writer = port.writable.getWriter();
  const reader = port.readable.getReader();
  let onData = () => {};
  let onClose = () => {};
  let closed = false;
  const finish = () => { if (!closed) { closed = true; onClose(); } };
  (async () => {
    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        if (value && value.length) onData(value);
      }
    } catch { /* device unplugged or rebooted */ }
    finish();
  })();
  return {
    write: (bytes) => writer.write(bytes),
    onData: (cb) => { onData = cb; },
    onClose: (cb) => { onClose = cb; if (closed) cb(); },
    async close() {
      closed = true;
      try { await reader.cancel(); } catch { /* ignore */ }
      try { reader.releaseLock(); } catch { /* ignore */ }
      try { await writer.close(); } catch { /* ignore */ }
      try { await port.close(); } catch { /* ignore */ }
      onClose();
    },
  };
}

export const serialSupported = (nav = globalThis.navigator) => Boolean(nav && 'serial' in nav);
