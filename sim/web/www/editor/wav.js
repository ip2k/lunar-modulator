// Bounded PCM WAV writer. More than two channels are discrete stereo stems,
// not a surround speaker layout: WAVE_FORMAT_EXTENSIBLE channel mask is zero.
export function createWav({frames, channels, sampleRate, bits = 24, maxBytes = 256 * 1024 * 1024}) {
  if (!Number.isSafeInteger(frames) || frames < 0 || !Number.isInteger(channels) || channels < 1 || channels > 8 || !Number.isInteger(sampleRate) || sampleRate < 8000 || sampleRate > 192000 || ![16, 24].includes(bits)) throw new RangeError('Invalid WAV dimensions.');
  const bytes = bits / 8, header = channels > 2 ? 68 : 44, dataBytes = frames * channels * bytes, size = header + dataBytes + (dataBytes & 1);
  if (!Number.isSafeInteger(size) || size > maxBytes || size - 8 > 0xffffffff) throw new RangeError('WAV exceeds the export memory or RIFF size limit.');
  const buffer = new ArrayBuffer(size), view = new DataView(buffer);
  const ascii = (offset, text) => [...text].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
  ascii(0, 'RIFF'); ascii(8, 'WAVE'); ascii(12, 'fmt ');
  view.setUint32(16, channels > 2 ? 40 : 16, true); view.setUint16(20, channels > 2 ? 0xfffe : 1, true);
  view.setUint16(22, channels, true); view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * channels * bytes, true); view.setUint16(32, channels * bytes, true); view.setUint16(34, bits, true);
  if (channels > 2) {
    view.setUint16(36, 22, true); view.setUint16(38, bits, true); view.setUint32(40, 0, true);
    new Uint8Array(buffer, 44, 16).set([1,0,0,0,0,0,16,0,128,0,0,170,0,56,155,113]);
  }
  ascii(header - 8, 'data'); let peak = 0, clipped = 0;
  return {
    writeBlock(offset, values, sourceChannels = channels, channelOffset = 0) {
      const count = values.length / sourceChannels;
      if (!Number.isInteger(sourceChannels) || sourceChannels < 1 || !Number.isInteger(channelOffset) || !Number.isInteger(count) || !Number.isInteger(offset) || offset < 0 || offset + count > frames || channelOffset < 0 || channelOffset + sourceChannels > channels) throw new RangeError('PCM block is outside the WAV.');
      for (let f = 0; f < count; ++f) for (let c = 0; c < sourceChannels; ++c) {
        const value = values[f * sourceChannels + c]; if (!Number.isFinite(value)) throw new Error('Renderer produced non-finite audio.');
        peak = Math.max(peak, Math.abs(value)); if (Math.abs(value) > 1) ++clipped;
        const x = Math.max(-1, Math.min(1, value)), q = Math.round(x * (x < 0 ? 2 ** (bits - 1) : 2 ** (bits - 1) - 1));
        const at = header + ((offset + f) * channels + channelOffset + c) * bytes;
        if (bits === 16) view.setInt16(at, q, true);
        else { view.setUint8(at, q & 255); view.setUint8(at + 1, (q >> 8) & 255); view.setUint8(at + 2, (q >> 16) & 255); }
      }
    },
    finish(samples = frames) {
      if (!Number.isSafeInteger(samples) || samples < 0 || samples > frames) throw new RangeError('Invalid final WAV length.');
      const dataLength = samples * channels * bytes, length = header + dataLength + (dataLength & 1);
      view.setUint32(4, length - 8, true); view.setUint32(header - 4, dataLength, true);
      if (dataLength & 1) view.setUint8(header + dataLength, 0);
      return {buffer: length === size ? buffer : buffer.slice(0, length), channels, samples, sampleRate, bits, peak, clipped};
    }
  };
}
