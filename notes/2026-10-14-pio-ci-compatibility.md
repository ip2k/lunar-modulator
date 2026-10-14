# PIO emulator dependency compatibility

## Cause

CI at the supplied failing run installed rp2040-pio-emulator==0.86.0; its
pioemu.emulate() signature has out_base/out_count but no set_base or
set_count. Import-time waveform construction in dongle/sim/pio_waveform.py
passes both SET pin arguments, so collection of tests/test_dongle_model.py
raises TypeError before tests run. The project had no emulator version pin.

The dependency resolver selected 0.86.0 because the transitive installer test
requirements pinned pytest==8.4.2. PyPI metadata for emulator 0.87.0 and
0.88.0 requires pytest >=9.0.2,<10.0.0, so those releases were incompatible
with that exact pin and pip backtracked. Emulator 0.88.0 restores set_base
and set_count; PyPI release metadata and its published wheel confirm that
signature.

## Change

- requirements-dev.txt pins rp2040-pio-emulator==0.88.0.
- tools/installer_service/requirements-test.txt changes the pytest pin to
  >=9.0.2,<10.0.0, matching emulator 0.88.0's declared range while keeping
  the major release bounded.

This keeps the maintained PIO emulator and existing waveform test design. It
avoids a custom SET-pin emulation shim and avoids changing PIO firmware or the
co-simulation. The API was checked against the published 0.86.0 and 0.88.0
wheels and the maintainer source:
https://github.com/NathanY3G/rp2040-pio-emulator and
https://pypi.org/project/rp2040-pio-emulator/0.88.0/.

## Checks

Using a temporary Python 3.12.15 Hera venv installed from this worktree's full
requirements-dev.txt:

- pip check: no broken requirements.
- python -m pytest -q tests/test_usb_key_pio.py tests/test_dongle_model.py:
  17 passed; this exercises both generated PIO waveforms and the existing ROM
  / dongle co-simulation.
- python -m pytest --collect-only -q: completed for the full test tree without
  collection errors (the previous failure was at this stage). FastAPI emitted
  an existing Starlette/httpx deprecation warning.

No device or hardware commands were used. These checks establish dependency
and host-simulation compatibility only, not physical dongle behavior.
