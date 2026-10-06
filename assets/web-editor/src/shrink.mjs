// shrink.mjs -- rewrites the rendered PNGs (8-bit RGB from Chromium) as 8-bit palette
// PNGs when the picture has 256 colours or fewer after a light snap, else as RGB with
// per-row filter choice and zlib level 9. No npm packages. The mockups are flat UI
// pictures, so the palette form loses nothing a reader can see.
//   node shrink.mjs ../*.png
import { readFileSync, writeFileSync } from 'node:fs';
import { inflateSync, deflateSync, crc32 } from 'node:zlib';

function chunks(b) {
  const out = []; let p = 8;
  while (p < b.length) {
    const n = b.readUInt32BE(p), t = b.toString('latin1', p + 4, p + 8);
    out.push({ t, d: b.subarray(p + 8, p + 8 + n) }); p += 12 + n;
  }
  return out;
}
function decode(buf) {
  const cs = chunks(buf), ih = cs.find((c) => c.t === 'IHDR').d;
  const w = ih.readUInt32BE(0), h = ih.readUInt32BE(4);
  if (ih[8] !== 8 || ih[9] !== 2 || ih[12] !== 0) throw new Error('want 8-bit RGB, not interlaced');
  const raw = inflateSync(Buffer.concat(cs.filter((c) => c.t === 'IDAT').map((c) => c.d)));
  const bpp = 3, stride = w * bpp, px = Buffer.alloc(h * stride);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (stride + 1)], src = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1));
    const cur = px.subarray(y * stride, (y + 1) * stride), prev = y ? px.subarray((y - 1) * stride, y * stride) : null;
    for (let x = 0; x < stride; x++) {
      const a = x >= bpp ? cur[x - bpp] : 0, b = prev ? prev[x] : 0, c = prev && x >= bpp ? prev[x - bpp] : 0;
      let v = src[x];
      if (f === 1) v += a; else if (f === 2) v += b; else if (f === 3) v += (a + b) >> 1;
      else if (f === 4) { const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c); v += pa <= pb && pa <= pc ? a : pb <= pc ? b : c; }
      cur[x] = v & 255;
    }
  }
  return { w, h, px };
}
function chunk(t, d) {
  const len = Buffer.alloc(4); len.writeUInt32BE(d.length);
  const td = Buffer.concat([Buffer.from(t, 'latin1'), d]);
  const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(td) >>> 0);
  return Buffer.concat([len, td, crc]);
}
function encode(w, h, rows, bpp, colourType, plte) {
  const stride = w * bpp, out = Buffer.alloc(h * (stride + 1));
  for (let y = 0; y < h; y++) {
    const cur = rows.subarray(y * stride, (y + 1) * stride), prev = y ? rows.subarray((y - 1) * stride, y * stride) : null;
    let best = null, bestSum = Infinity, bestF = 0;
    for (const f of (bpp === 1 ? [0, 1, 2] : [0, 1, 2, 3, 4])) {
      const line = Buffer.alloc(stride); let sum = 0;
      for (let x = 0; x < stride; x++) {
        const a = x >= bpp ? cur[x - bpp] : 0, b = prev ? prev[x] : 0, c = prev && x >= bpp ? prev[x - bpp] : 0;
        let p = 0;
        if (f === 1) p = a; else if (f === 2) p = b; else if (f === 3) p = (a + b) >> 1;
        else if (f === 4) { const q = a + b - c, pa = Math.abs(q - a), pb = Math.abs(q - b), pc = Math.abs(q - c); p = pa <= pb && pa <= pc ? a : pb <= pc ? b : c; }
        const v = (cur[x] - p) & 255; line[x] = v; sum += v < 128 ? v : 256 - v;
      }
      if (sum < bestSum) { bestSum = sum; best = line; bestF = f; }
    }
    out[y * (stride + 1)] = bestF; best.copy(out, y * (stride + 1) + 1);
  }
  const ih = Buffer.alloc(13); ih.writeUInt32BE(w, 0); ih.writeUInt32BE(h, 4); ih[8] = 8; ih[9] = colourType;
  const parts = [Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ih)];
  if (plte) parts.push(chunk('PLTE', plte));
  parts.push(chunk('IDAT', deflateSync(out, { level: 9, memLevel: 9 })), chunk('IEND', Buffer.alloc(0)));
  return Buffer.concat(parts);
}
// 256 colours: the 168 most used exactly, then a median cut of the rest, weighted by use.
function palette(px) {
  const count = new Map();
  for (let i = 0; i < px.length; i += 3) { const k = (px[i] << 16) | (px[i + 1] << 8) | px[i + 2]; count.set(k, (count.get(k) || 0) + 1); }
  const cols = [...count.entries()].map(([k, n]) => [k >> 16, (k >> 8) & 255, k & 255, n]);
  if (cols.length <= 256) return cols.map((c) => c.slice(0, 3));
  // Keep the most used exact colours (the flat fills: grounds, the role colours, the
  // sound colours) and median-cut only the rest (antialiased edges).
  cols.sort((a, b) => b[3] - a[3]);
  const keep = cols.slice(0, 168).map((c) => c.slice(0, 3));
  let boxes = [cols.slice(168)];
  while (boxes.length < 256 - keep.length) {
    boxes.sort((a, b) => b.reduce((s, c) => s + c[3], 0) * spread(b) - a.reduce((s, c) => s + c[3], 0) * spread(a));
    const box = boxes.shift(); if (box.length < 2) { boxes.push(box); break; }
    const ch = widest(box); box.sort((a, b) => a[ch] - b[ch]);
    const total = box.reduce((s, c) => s + c[3], 0); let acc = 0, cut = 1;
    for (let i = 0; i < box.length - 1; i++) { acc += box[i][3]; if (acc >= total / 2) { cut = i + 1; break; } }
    boxes.push(box.slice(0, cut), box.slice(cut));
  }
  return keep.concat(boxes.map((b) => { const n = b.reduce((s, c) => s + c[3], 0); return [0, 1, 2].map((i) => Math.round(b.reduce((s, c) => s + c[i] * c[3], 0) / n)); }));
  function widest(b) { let best = 0, r = -1; for (let i = 0; i < 3; i++) { const v = b.map((c) => c[i]); const d = Math.max(...v) - Math.min(...v); if (d > r) { r = d; best = i; } } return best; }
  function spread(b) { let r = 0; for (let i = 0; i < 3; i++) { let lo = 255, hi = 0; for (const c of b) { lo = Math.min(lo, c[i]); hi = Math.max(hi, c[i]); } r = Math.max(r, hi - lo); } return r; }
}
for (const f of process.argv.slice(2)) {
  const before = readFileSync(f), { w, h, px } = decode(before);
  const pal = palette(px), cache = new Map(), idx = Buffer.alloc(w * h);
  for (let i = 0, j = 0; i < px.length; i += 3, j++) {
    const k = (px[i] << 16) | (px[i + 1] << 8) | px[i + 2];
    let n = cache.get(k);
    if (n === undefined) {
      let bd = Infinity; n = 0;
      for (let q = 0; q < pal.length; q++) { const d = (pal[q][0] - px[i]) ** 2 * 2 + (pal[q][1] - px[i + 1]) ** 2 * 4 + (pal[q][2] - px[i + 2]) ** 2 * 3; if (d < bd) { bd = d; n = q; } }
      cache.set(k, n);
    }
    idx[j] = n;
  }
  const after = encode(w, h, idx, 1, 3, Buffer.from(pal.flat()));
  writeFileSync(f, after);
  console.log(`${f}: ${before.length} -> ${after.length} B, ${cache.size} colours -> ${pal.length}`);
}
