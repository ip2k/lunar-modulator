#!/usr/bin/env python3
"""Mandatory target pinning for every tool that opens a mask-ROM (4c4a:8057) device.

The AC79 dev kit and the FM-1 both enumerate as USB 4c4a:8057 in ROM mode, so a
VID:PID match cannot tell them apart. A tool names its role (`fm1` or
`devkit`, fixed in the tool, never guessed) and the caller names the sysfs
bus-port path (`--usb-path`, e.g. `1-2` or `3-1.2`). This module then refuses
unless all of these hold:

* the path is well formed and matches the role in the config file
  (`tools/bench_targets.json`, or the file named by FM1_BENCH_TARGETS):
  an exact `paths` entry when the role lists any, otherwise a `buses` entry;
* the path is not an exact path of the other role;
* exactly one 4c4a:8057 device is present on the host (two present is ambiguous
  even when one is the requested one), and it is the one at that path;
* the SCSI-generic node resolves to a USB device at that path that is 4c4a:8057
  (and to the expected devnum, when the caller gives one).

It only reads sysfs; it opens no device node. MIT licence.
"""
import json
import os
import stat as stat_mod
from pathlib import Path
import re

ROM_ID = ('4c4a', '8057')
ROLES = ('fm1', 'devkit')
USB_ROOT = Path('/sys/bus/usb/devices')
SG_ROOT = Path('/sys/class/scsi_generic')
# Hooks so tests can stand in for the real /dev node and its stat.
_stat = os.stat
_resolve = os.path.realpath
DEFAULT_CONFIG = Path(__file__).with_name('bench_targets.json')
PATH_RE = re.compile(r'^[1-9][0-9]*-[1-9][0-9]*(\.[1-9][0-9]*)*$')


class PinError(ValueError):
    """The requested target could not be pinned; no device was opened."""


def load_config(path=None):
    path = Path(path or os.environ.get('FM1_BENCH_TARGETS') or DEFAULT_CONFIG)
    try:
        cfg = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise PinError(f'Cannot read bench target config {path}: {exc}') from exc
    roles = cfg.get('roles') if isinstance(cfg, dict) else None
    if not isinstance(roles, dict) or set(roles) != set(ROLES):
        raise PinError(f'{path}: "roles" must define exactly {", ".join(ROLES)}')
    for name, entry in roles.items():
        paths, buses = entry.get('paths', []), entry.get('buses', [])
        if (not isinstance(paths, list) or not isinstance(buses, list)
                or not all(isinstance(p, str) and PATH_RE.match(p) for p in paths)
                or not all(isinstance(b, int) and not isinstance(b, bool) and b > 0 for b in buses)
                or not (paths or buses)):
            raise PinError(f'{path}: role {name} needs valid paths and/or buses')
    if set(roles['fm1'].get('buses', [])) & set(roles['devkit'].get('buses', [])):
        raise PinError(f'{path}: fm1 and devkit must not share a bus')
    if set(roles['fm1'].get('paths', [])) & set(roles['devkit'].get('paths', [])):
        raise PinError(f'{path}: fm1 and devkit must not share a path')
    return cfg


def bus_of(usb_path):
    return int(usb_path.split('-', 1)[0])


def check_role_path(role, usb_path, config=None):
    """Config-only check: is this bus-port path allowed for this role?"""
    if role not in ROLES:
        raise PinError(f'Unknown role {role!r}; expected one of {", ".join(ROLES)}')
    if not isinstance(usb_path, str) or not PATH_RE.match(usb_path):
        raise PinError(f'--usb-path must be a sysfs bus-port such as 1-2 or 3-1.2, got {usb_path!r}')
    roles = (config or load_config())['roles']
    other_name = 'devkit' if role == 'fm1' else 'fm1'
    mine = roles[role]
    if usb_path in roles[other_name].get('paths', []):
        raise PinError(f'{usb_path} is the {other_name} port, not the {role}')
    if mine.get('paths'):
        if usb_path not in mine['paths']:
            raise PinError(f'{usb_path} is not a configured {role} path {mine["paths"]}')
    elif bus_of(usb_path) not in mine.get('buses', []):
        raise PinError(f'{usb_path} is not on a configured {role} bus {mine.get("buses")}')


def _read(p, name):
    try:
        return (p / name).read_text().strip()
    except OSError:
        return None


def rom_devices(usb_root=USB_ROOT):
    """Every 4c4a:8057 device on the host as {'path', 'devnum', 'dir'}."""
    out = []
    for p in sorted(Path(usb_root).glob('*')):
        vid, pid = _read(p, 'idVendor'), _read(p, 'idProduct')
        if vid and pid and (vid.lower(), pid.lower()) == ROM_ID:
            out.append({'path': p.name, 'devnum': _read(p, 'devnum'), 'dir': p})
    return out


def sg_usb_device(device, sg_root=SG_ROOT):
    """The USB device directory behind a /dev/sgN node, or None.

    The node must be the real /dev/sgN character device whose major:minor is the
    one sysfs lists for sgN, so a symlink or a copy cannot stand in for it."""
    name = Path(device).name
    if not re.fullmatch(r'sg[0-9]+', name):
        raise PinError(f'Expected a /dev/sgN SCSI-generic node, got {device!r}')
    if _resolve(str(device)) != '/dev/' + name:
        raise PinError(f'{device} does not resolve to /dev/{name}')
    try:
        st = _stat(device)
        listed = (Path(sg_root) / name / 'dev').read_text().strip()
    except OSError as e:
        raise PinError(f'Cannot verify {device} against sysfs: {e}')
    if not stat_mod.S_ISCHR(st.st_mode) or listed != '%d:%d' % (os.major(st.st_rdev), os.minor(st.st_rdev)):
        raise PinError(f'{device} is not the character device sysfs lists for {name} ({listed})')
    link = Path(sg_root) / name / 'device'
    if not link.exists():
        raise PinError(f'No sysfs entry for {name}')
    resolved = link.resolve()
    for ancestor in [resolved, *resolved.parents]:
        if (ancestor / 'idVendor').exists():
            return ancestor
    return None


def pin_rom_target(role, usb_path, device, *, devnum=None, config=None, log=None,
                   usb_root=USB_ROOT, sg_root=SG_ROOT):
    """Validate and return {'role','path','devnum','dir'} for one ROM device.

    Raises PinError before any device node is opened."""
    check_role_path(role, usb_path, config)
    present = rom_devices(usb_root)
    if len(present) > 1:
        raise PinError('More than one 4c4a:8057 device present (%s); disconnect all but the %s'
                       % (', '.join(d['path'] for d in present), role))
    if not present:
        raise PinError('No 4c4a:8057 ROM device present')
    if present[0]['path'] != usb_path:
        raise PinError(f'The only 4c4a:8057 device is at {present[0]["path"]}, not the requested '
                       f'{role} path {usb_path}')
    usb = sg_usb_device(device, sg_root)
    if usb is None or usb.name != usb_path:
        raise PinError(f'{device} is not on USB path {usb_path}')
    if ((_read(usb, 'idVendor') or '').lower(), (_read(usb, 'idProduct') or '').lower()) != ROM_ID:
        raise PinError('SG device is not USB 4c4a:8057 UBOOT')
    actual = _read(usb, 'devnum')
    if devnum is not None and actual != str(devnum):
        raise PinError(f'USB devnum is {actual}, expected {devnum}; connection changed')
    target = {'role': role, 'path': usb_path, 'devnum': actual, 'dir': usb}
    if log:
        log('target_pinned', role=role, usb_path=usb_path, devnum=actual, device=str(device))
    return target
