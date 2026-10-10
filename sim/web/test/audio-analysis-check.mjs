// Prove the external-audio detector rejects silent and held/skipped output.
import assert from 'node:assert/strict';
import { toneAnalysis } from './audio-analysis.mjs';
const rate = 48000, seconds = 5;
const make = () => Float32Array.from({ length: (seconds + 2) * rate * 2 }, (_, i) => 0.1 * Math.sin(2 * Math.PI * 440 * Math.floor(i / 2) / rate));
assert.equal(toneAnalysis(make(), seconds).pass, true);
const silent = make(); silent.fill(0, rate * 2, rate * 2 + 256);
assert.equal(toneAnalysis(silent, seconds).pass, false);
const held = make(); held.fill(held[rate * 2], rate * 2, rate * 2 + 256);
assert.equal(toneAnalysis(held, seconds).pass, false);
const skipped = make(); skipped.set(skipped.slice(rate * 2 + 256), rate * 2);
assert.equal(toneAnalysis(skipped, seconds).pass, false);
const right = make(); for (let i = rate * 2 + 1; i < rate * 2 + 257; i += 2) right[i] = 0;
assert.equal(toneAnalysis(right, seconds).pass, false);
assert.equal(toneAnalysis(new Float32Array(rate * 2), seconds).pass, false);
console.log('audio detector: clean tone passes; silence, held block, phase skip, right-channel loss and no output fail');
