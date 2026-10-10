// Float32 stereo PulseAudio monitor analysis. MIT licence.
// Sustained 440 Hz sine: silence >=128 samples and cycle errors >2 samples
// are failures. This detects zero fills, held/repeated blocks and phase skips;
// it does not certify arbitrary music, sub-sample defects or physical devices.
export function toneAnalysis(stereo, seconds, rate = 48000) {
  const mono = [];
  let nonfinite = 0, channelMismatches = 0;
  for (let i = 0; i < stereo.length; i += 2) {
    if (!Number.isFinite(stereo[i]) || !Number.isFinite(stereo[i + 1])) nonfinite++;
    if (Math.abs(stereo[i] - stereo[i + 1]) > 0.00001) channelMismatches++;
    mono.push(stereo[i]);
  }
  const first = mono.findIndex(x => Math.abs(x) > 0.005);
  let last = mono.length - 1;
  while (last >= 0 && !(Math.abs(mono[last]) > 0.005)) last--;
  const activeSeconds = Math.max(0, last - first) / rate;
  // Exclude note attack/release and capture startup/shutdown, not internal gaps.
  const start = first + Math.round(rate / 4), end = last - Math.round(rate / 4);
  let zeroRun = 0, maxZeroRun = 0, crossing = null, maxPeriodError = 0, badPeriods = 0, cycles = 0;
  for (let i = Math.max(1, start); i < end; i++) {
    zeroRun = Math.abs(mono[i]) < 0.00001 ? zeroRun + 1 : 0;
    maxZeroRun = Math.max(maxZeroRun, zeroRun);
    if (mono[i - 1] <= 0 && mono[i] > 0) {
      // Linear interpolation avoids quantization of the measured crossing.
      const at = i - 1 - mono[i - 1] / (mono[i] - mono[i - 1]);
      if (crossing !== null) {
        const error = Math.abs(at - crossing - rate / 440);
        maxPeriodError = Math.max(maxPeriodError, error);
        if (error > 2) badPeriods++;
        cycles++;
      }
      crossing = at;
    }
  }
  return { pass: !nonfinite && !channelMismatches && activeSeconds >= seconds + 1 && maxZeroRun < 128 && !badPeriods && cycles > seconds * 400,
    activeSeconds, nonfinite, channelMismatches, maxZeroRun, maxSilenceMs: maxZeroRun * 1000 / rate, cycles, badPeriods, maxPeriodError };
}
export function pcmWave(stereo, rate = 48000) {
  const b = Buffer.alloc(44 + stereo.length * 2);
  b.write('RIFF'); b.writeUInt32LE(b.length - 8, 4); b.write('WAVEfmt ', 8);
  b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20); b.writeUInt16LE(2, 22);
  b.writeUInt32LE(rate, 24); b.writeUInt32LE(rate * 4, 28); b.writeUInt16LE(4, 32); b.writeUInt16LE(16, 34);
  b.write('data', 36); b.writeUInt32LE(stereo.length * 2, 40);
  for (let i = 0; i < stereo.length; i++) b.writeInt16LE(Math.round(Math.max(-1, Math.min(1, stereo[i])) * 32767), 44 + i * 2);
  return b;
}
