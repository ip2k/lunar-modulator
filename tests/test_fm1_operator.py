"""Numerical properties and independently derived edge vectors of the V15 model."""

import math

import pytest

from tools.fm1_dsp import log_sine_lookup_stage
from tools.fm1_operator import (OperatorState, attenuation_ramp, lookup_sample_word,
                                render_three_operator_block)


def state(start=8000, target=8000, increment=0, phase=0):
    return OperatorState(start, (16384 - target) << 14, increment, phase)


@pytest.mark.parametrize("start,target,first,last", [
    (8000, 8063, 8001, 8064),
    (8000, 7968, 8000, 8000),
    (16352, 16384, 16353, 16416),
    (63, 0, 62, -1),
    (0, 16384, 16383, 16383),
])
def test_ramp_endpoints_and_zero_sentinel(start, target, first, last):
    converted, samples = attenuation_ramp(state(start, target))
    assert converted == target
    assert len(samples) == 64
    assert (samples[0], samples[-1]) == (first, last)


def test_register_lookup_agrees_with_independent_bounded_scalar_model():
    for cell in range(4096):
        for attenuation in (0, 1024, 8192, 16384):
            scalar_bits = (log_sine_lookup_stage(cell << 12, attenuation) << 13) & 0xFFFFFFFF
            assert lookup_sample_word(cell << 12, attenuation) & 0xFFFFFFFF == scalar_bits


def test_underflow_sign_comes_from_combined_logarithm():
    # At the peak the log-sine value is zero. -1 sets all low bits, selects
    # exponent entry zero, and shifts by31; signed-halfword selection remains.
    assert lookup_sample_word(1023 << 12, -1) == -8192
    assert lookup_sample_word(3071 << 12, -1) == 0
    assert lookup_sample_word(1023 << 12, 0xFFFFFFFF) == -8192


def test_silent_modulators_leave_analytic_carrier_in_positive_quarter():
    # Modulators at maximal attenuation yield zero throughout this positive
    # quarter, even with the carrier's feedback. Compare the carrier to sin,
    # rather than calling our lookup function to compute the expected vector.
    states = (state(16384, 16384), state(16384, 16384), state(1, 1, 16 << 12))
    result = render_three_operator_block(states)
    assert len(result.samples) == 64
    for sample, actual in enumerate(result.samples):
        ideal = math.sin((sample * 16 + 0.5) * 2 * math.pi / 4096) * 8192 * 2 ** (-2 / 1024)
        assert abs(actual / 8192 - ideal) < 4
    assert result.feedback == result.samples[-2:]
    assert result.target_attenuations == (16384, 16384, 1)
    assert result.working_phases == (0, 0, 64 * (16 << 12))
    assert states[2].phase == 0


def test_phase_and_feedback_words_have_signed_unsigned_equivalence():
    signed_states = tuple(state(10000, 10000, -5, -10) for _ in range(3))
    unsigned_states = tuple(state(10000, 10000, 0xFFFFFFFB, 0xFFFFFFF6) for _ in range(3))
    signed = render_three_operator_block(signed_states, (-1, -2147483648))
    unsigned = render_three_operator_block(unsigned_states, (0xFFFFFFFF, 0x80000000))
    assert signed == unsigned
    assert signed.working_phases == (0xFFFFFEB6,) * 3


@pytest.mark.parametrize("kwargs", [{"previous_attenuation": -1}, {"level": -1},
                                    {"level": 268435457}, {"phase": 1 << 32},
                                    {"phase_increment": True}])
def test_state_domain_is_explicit(kwargs):
    fields = dict(previous_attenuation=1000, level=10000, phase=0, phase_increment=1)
    fields.update(kwargs)
    with pytest.raises(ValueError):
        OperatorState(**fields)


@pytest.mark.parametrize("states,history,shift", [
    ((), (0, 0), 16), ((state(),) * 3, (0,), 16),
    ((state(),) * 3, (0, 0), 17), ((state(),) * 3, (0, 0), 1),
])
def test_kernel_domain_is_explicit(states, history, shift):
    with pytest.raises(ValueError):
        render_three_operator_block(states, history, kernel_feedback_shift=shift)
