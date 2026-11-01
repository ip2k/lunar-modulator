# SPDX-License-Identifier: MIT
"""Explicit runtime selection; neither mode establishes release admission."""
MODES = ('diagnostic', 'song-diagnostic', 'continuous')


def runtime_configuration(mode):
    if mode not in MODES:
        raise ValueError('Unknown native runtime mode')
    seconds = {'diagnostic': 20, 'song-diagnostic': 120, 'continuous': 0}[mode]
    return dict(runtime_mode=mode, return_to_rom_seconds=seconds or None,
                define='-DLUNAR_RETURN_TO_ROM_SECONDS=' + str(seconds),
                release_accepted=False)
