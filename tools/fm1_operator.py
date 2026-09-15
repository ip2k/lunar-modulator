"""Offline reconstruction of the V15 three-operator kernel.

This models the inspected integer data flow, including overflow and attenuation
rounding. It is not an instruction emulator or a complete FM-1 voice renderer.
There is no hardware I/O. See docs/17-operator-abi.md for the byte evidence.
"""

from dataclasses import dataclass

try:
    from .fm1_dsp import exponent_table, log_sine_table
except ImportError:
    from fm1_dsp import exponent_table, log_sine_table


BLOCK_SIZE = 64
APPLICATION_SHA256 = "306e47065f35d7a7a05ada7f5dd092f6e770952054f33f0a86b75fd10ffe3203"


def _s32(value: int) -> int:
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value & (1 << 31) else value


def _is_word(value: int) -> bool:
    return type(value) is int and -(1 << 31) <= value < (1 << 32)


@dataclass(frozen=True)
class OperatorState:
    """Interpretation of one 16-byte state immediately before rendering.

    level is the pre-render field at +4; it is not linear amplitude. Zero in
    previous_attenuation is the initialization sentinel, not full amplitude.
    Phase values may use signed or unsigned representations of a 32-bit word.
    """

    previous_attenuation: int
    level: int
    phase_increment: int
    phase: int

    def __post_init__(self):
        if type(self.previous_attenuation) is not int or not 0 <= self.previous_attenuation <= 16384:
            raise ValueError("previous attenuation must be in 0..16384")
        if type(self.level) is not int or not 0 <= self.level <= 16384 << 14:
            raise ValueError("level must be in 0..268435456")
        if not _is_word(self.phase) or not _is_word(self.phase_increment):
            raise ValueError("phase and phase increment must be 32-bit words")


@dataclass(frozen=True)
class OperatorBlock:
    """Predicted outputs and state values, without modifying input states.

    The actual kernel writes feedback and target attenuations. Its working
    phases are returned here for analysis; their persistence is the caller's
    responsibility in the firmware.
    """

    samples: tuple[int, ...]
    feedback: tuple[int, int]
    target_attenuations: tuple[int, int, int]
    working_phases: tuple[int, int, int]


def attenuation_ramp(state: OperatorState) -> tuple[int, tuple[int, ...]]:
    """Return converted target and all 64 sample attenuations.

    The rounded step can miss its target by -31..32. Intermediate values can
    therefore leave 0..16384 even when both endpoints lie within that range.
    """
    if not isinstance(state, OperatorState):
        raise ValueError("an OperatorState is required")
    start = state.previous_attenuation or 16383
    target = 16384 - (state.level >> 14)
    step = (target - start + 32) >> 6
    return target, tuple(start + (sample + 1) * step for sample in range(BLOCK_SIZE))


def lookup_sample_word(phase: int, attenuation: int) -> int:
    """Exact reconstructed register arithmetic of the inspected lookup stage.

    Returns the signed 32-bit value after the kernel's <<13 conversion. Unlike
    fm1_dsp.log_sine_lookup_stage, this retains the sign-bit behavior when an
    attenuation ramp underflows. Sign is taken from the low signed halfword of
    the combined logarithm, not unconditionally from the phase quadrant.
    """
    if not _is_word(phase) or not _is_word(attenuation):
        raise ValueError("phase and attenuation must be 32-bit words")
    position = ((phase & 0xFFFFFFFF) >> 12) & 4095
    index = position & 1023
    if position & 1024:
        index ^= 1023
    logarithm = log_sine_table()[index]
    if position & 2048:
        logarithm |= 0xFFFF8000
    combined = (logarithm + attenuation) & 0xFFFFFFFF
    magnitude = (exponent_table()[(~combined) & 1023] + 4096) >> ((combined >> 10) & 31)
    register = (magnitude | 0x70000) ^ 0xFFFF if combined & 0x8000 else magnitude
    return _s32(register << 13)


def render_three_operator_block(states: tuple[OperatorState, OperatorState, OperatorState],
                                feedback: tuple[int, int] = (0, 0), *,
                                kernel_feedback_shift: int = 16) -> OperatorBlock:
    """Reconstruct the fixed 64-sample V15 cascade, for a bounded input domain.

    kernel_feedback_shift is the already adjusted argument at entry stack +4.
    For ordinary nonnegative voice input, its caller passes
    min(voice_feedback_shift + 2, 16). The kernel adds one more before shifting.
    The feedback source is the final third-operator output. Output is assigned,
    not accumulated. Other algorithm branches and the voice mixer are excluded.
    """
    if not isinstance(states, (tuple, list)) or len(states) != 3 or not all(isinstance(s, OperatorState) for s in states):
        raise ValueError("exactly three OperatorState values are required")
    if not isinstance(feedback, (tuple, list)) or len(feedback) != 2 or not all(_is_word(v) for v in feedback):
        raise ValueError("feedback must contain two 32-bit words")
    if type(kernel_feedback_shift) is not int or not 2 <= kernel_feedback_shift <= 16:
        raise ValueError("kernel feedback shift must be in 2..16")
    ramps = [attenuation_ramp(state) for state in states]
    phases = [state.phase & 0xFFFFFFFF for state in states]
    old, recent = map(_s32, feedback)
    output = []
    for sample in range(BLOCK_SIZE):
        modulation = _s32(old + recent) >> (kernel_feedback_shift + 1)
        for operator, state in enumerate(states):
            phase = (phases[operator] + modulation) & 0xFFFFFFFF
            modulation = lookup_sample_word(phase, ramps[operator][1][sample])
            phases[operator] = (phases[operator] + state.phase_increment) & 0xFFFFFFFF
        output.append(modulation)
        old, recent = recent, modulation
    return OperatorBlock(tuple(output), (old, recent), tuple(r[0] for r in ramps), tuple(phases))
