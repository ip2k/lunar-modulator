#!/usr/bin/env python3
"""MIT. Bounded-memory screening of a captured reference tone, not music QA.

Uses the standard wave/array readers; accepts interleaved PCM16/PCM32, including
KA6 six-channel PCM32. Analyze each channel independently. Zero-crossing cadence
with hysteresis detects gaps/held blocks/phase skips above the stated tolerance;
it cannot prove absence of every click, distortion, or sample-sized defect.
Combine with IRQ counters, capture transport evidence and listening.
"""
import argparse
import array
import json
import math
import sys
import wave


class ToneChannel:
    def __init__(self, rate, frequency=997., tolerance_samples=2.):
        self.rate, self.frequency, self.tolerance = rate, frequency, tolerance_samples
        self.frames = self.cycles = self.bad_periods = self.clipped = 0
        self.energy = self.peak = self.max_period_error = 0.
        self.previous = self.crossing = self.first_crossing = None
        self.armed = False
        self.pending = None
        self.examples = []

    def feed(self, samples):
        if not samples:
            return
        # A fixed floor prevents a silent/noise-only window arming at zero.
        rms = math.sqrt(sum(x*x for x in samples)/len(samples))
        threshold = max(0.0001, rms * 0.2)
        for x in samples:
            at = self.frames
            self.frames += 1
            self.energy += x*x
            self.peak = max(self.peak, abs(x))
            self.clipped += abs(x) >= 0.999
            if x < -threshold:
                self.armed, self.pending = True, None
            if self.armed and self.previous is not None and self.previous <= 0 < x:
                self.pending = at - 1 - self.previous/(x-self.previous)
            if self.armed and self.pending is not None and x > threshold:
                crossing = self.pending
                if self.crossing is not None:
                    error = abs(crossing-self.crossing-self.rate/self.frequency)
                    self.max_period_error = max(self.max_period_error, error)
                    self.cycles += 1
                    if error > self.tolerance:
                        self.bad_periods += 1
                        if len(self.examples) < 20:
                            self.examples.append(crossing/self.rate)
                else:
                    self.first_crossing = crossing
                self.crossing = crossing
                self.armed, self.pending = False, None
            self.previous = x

    def report(self):
        duration = self.frames/self.rate
        rms = math.sqrt(self.energy/max(1,self.frames))
        hz = (self.cycles*self.rate/(self.crossing-self.first_crossing)
              if self.cycles and self.crossing != self.first_crossing else 0.)
        flags = []
        if duration < 1.: flags.append('less_than_one_second')
        if rms < 0.001: flags.append('weak_or_missing_signal')
        if self.cycles < max(0., duration-0.05)*self.frequency*0.98:
            flags.append('missing_cycles')
        if abs(hz-self.frequency) > self.frequency*0.02:
            flags.append('frequency_outside_2_percent')
        if self.bad_periods: flags.append('irregular_cycles')
        if self.clipped: flags.append('clipping')
        return dict(flags=flags, frames=self.frames, seconds=duration,
                    rms_dbfs=20*math.log10(max(rms,1e-15)), peak=self.peak,
                    measured_hz=hz, cycles=self.cycles, bad_periods=self.bad_periods,
                    max_period_error_samples=self.max_period_error,
                    tolerance_samples=self.tolerance, clipped_samples=self.clipped,
                    first_bad_seconds_after_skip=self.examples)


def analyze(path, channels=(1,2), skip_seconds=2., frequency=997., tolerance=2.):
    if skip_seconds < 0 or frequency <= 0 or tolerance <= 0:
        raise ValueError('Positive tone/tolerance and nonnegative startup skip required')
    with wave.open(str(path), 'rb') as src:
        count, width, rate = src.getnchannels(), src.getsampwidth(), src.getframerate()
        if (src.getcomptype() != 'NONE' or width not in (2,4)
                or not channels or any(c < 1 or c > count for c in channels)
                or frequency >= rate/2):
            raise ValueError('Expected PCM16/PCM32, valid 1-based channels and tone below Nyquist')
        src.setpos(min(src.getnframes(), round(skip_seconds*rate)))
        states = [ToneChannel(rate,frequency,tolerance) for _ in channels]
        while raw := src.readframes(rate):
            samples = array.array('h' if width == 2 else 'i')
            samples.frombytes(raw)
            if sys.byteorder != 'little': samples.byteswap()
            scale = float(1 << (8*width-1))
            for channel,state in zip(channels,states):
                state.feed([x/scale for x in samples[channel-1::count]])
        return dict(reference_only=True, certifies_dropout_free_music=False,
                    rate=rate, recorded_channels=count, startup_skip_seconds=skip_seconds,
                    expected_hz=frequency,
                    channels={str(c):s.report() for c,s in zip(channels,states)})


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('wave')
    ap.add_argument('--skip-seconds', type=float, default=2.)
    ap.add_argument('--frequency', type=float, default=997.)
    ap.add_argument('--tolerance-samples', type=float, default=2.)
    a = ap.parse_args()
    result = analyze(a.wave,skip_seconds=a.skip_seconds,frequency=a.frequency,
                     tolerance=a.tolerance_samples)
    print(json.dumps(result,indent=2))
    sys.exit(1 if any(c['flags'] for c in result['channels'].values()) else 0)
