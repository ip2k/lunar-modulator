# SPDX-License-Identifier: MIT
"""Explicit runtime selection; neither mode establishes release admission."""
MODES = ('diagnostic', 'continuous')


def runtime_configuration(mode):
    if mode not in MODES:
        raise ValueError('Unknown native runtime mode')
    seconds = 20 if mode == 'diagnostic' else 0
    return dict(runtime_mode=mode, return_to_rom_seconds=seconds or None,
                define='-DLUNAR_RETURN_TO_ROM_SECONDS=' + str(seconds),
                release_accepted=False)
