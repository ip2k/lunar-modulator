"""Capture detector acceptance and deliberate fault rejection; synthetic PCM only."""
import array
import importlib.util
import math
from pathlib import Path
import random
import sys
import wave

import pytest

spec = importlib.util.spec_from_file_location('tone',Path(__file__).parents[1]/'tools/devkit_tone_analysis.py')
tone = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tone)
RATE = 48000


def signal():
    rng = random.Random(23)
    # Slight clock mismatch and independent analog-like noise.
    return [0.1*math.sin(2*math.pi*997.2*i/RATE)+rng.uniform(-0.0003,0.0003)
            for i in range(RATE*2)]


def result(samples):
    state = tone.ToneChannel(RATE)
    # Force a chunk boundary through the middle of a cycle.
    for i in range(0,len(samples),1237): state.feed(samples[i:i+1237])
    return state.report()


def test_clock_drift_noise_and_chunk_boundaries():
    r = result(signal())
    assert not r['flags'], r
    assert abs(r['measured_hz']-997.2) < .1


@pytest.mark.parametrize('fault',['silence','held','skip','repeat','clip','noise'])
def test_faults_are_not_accepted(fault):
    a = signal()
    if fault == 'silence': a[RATE:RATE+256] = [0.]*256
    if fault == 'held': a[RATE:RATE+256] = [a[RATE]]*256
    if fault == 'skip': a[RATE:] = a[RATE+128:]
    if fault == 'repeat': a[RATE:RATE+128] = a[RATE-128:RATE]
    if fault == 'clip': a[RATE:RATE+20] = [1.]*20
    if fault == 'noise':
        rng = random.Random(1)
        a = [rng.uniform(-.05,.05) for _ in a]
    assert result(a)['flags']


def test_missing_or_short_signal():
    assert 'weak_or_missing_signal' in result([0.]*RATE)['flags']
    assert 'less_than_one_second' in result(signal()[:1000])['flags']


@pytest.mark.parametrize('width',[2,4])
def test_wave_six_channel_independent_routing(tmp_path,width):
    left = signal()
    samples = array.array('h' if width == 2 else 'i')
    scale = (1 << (8*width-1))-1
    for x in left: samples.extend([int(x*scale),0,0,0,0,0])
    if sys.byteorder != 'little': samples.byteswap()
    path = tmp_path/'ka6.wav'
    with wave.open(str(path),'wb') as dst:
        dst.setnchannels(6);dst.setsampwidth(width);dst.setframerate(RATE)
        dst.writeframes(samples.tobytes())
    r = tone.analyze(path,skip_seconds=0)
    assert not r['channels']['1']['flags']
    assert 'weak_or_missing_signal' in r['channels']['2']['flags']
    assert r['certifies_dropout_free_music'] is False
    with pytest.raises(ValueError): tone.analyze(path,channels=(7,))
