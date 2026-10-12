#!/usr/bin/python3
"""MIT. CLOSED one exact preparation-stop trace-read child; never retry."""
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import stat
import sys

STAGE = None
RUN = None
NATIVE_SHA = None
READER_SHA = None
PROOF_SHA = None
CAMPAIGN_SHA = None
STOP_SHA = None


def main():
    pins = (NATIVE_SHA, READER_SHA, PROOF_SHA, CAMPAIGN_SHA, STOP_SHA)
    if (any(type(p) is not str or not re.fullmatch('[0-9a-f]{64}', p) for p in pins)
            or not isinstance(STAGE, Path) or not isinstance(RUN, Path) or RUN.parent != STAGE
            or not STAGE.is_absolute() or not RUN.is_absolute()):
        raise ValueError('Closed child: concrete exact activation pins unaccepted')
    if sys.platform != 'linux' or os.geteuid() != 0 or sys.flags.optimize != 0:
        raise ValueError('Reviewed nonoptimized Linux root child required')
    def read(path):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        try:
            fp = os.fdopen(fd, 'rb')
        except BaseException:
            os.close(fd); raise
        with fp:
            if not stat.S_ISREG(os.fstat(fp.fileno()).st_mode):
                raise ValueError('Direct regular pinned input required')
            raw = fp.read(2 * 1048576 + 1)
        if len(raw) > 2 * 1048576:
            raise ValueError('Pinned input exceeds bound')
        return raw
    sources = ('fm1_sdk_prepare_stop_trace_read', 'fm1_sdk_trace_read', 'fm1_sdk_trace_prepare_stop')
    for name, pin in zip(sources, (NATIVE_SHA, READER_SHA, PROOF_SHA)):
        if hashlib.sha256(read(STAGE / 'tools' / (name + '.py'))).hexdigest() != pin:
            raise ValueError('Reviewed exact source differs')
    for name, pin in (('campaign.json', CAMPAIGN_SHA), ('preparation-stop.json', STOP_SHA)):
        if hashlib.sha256(read(RUN / name)).hexdigest() != pin:
            raise ValueError('Actual campaign differs')
    sys.path.insert(0, str(STAGE / 'tools'))
    native = importlib.import_module('fm1_sdk_prepare_stop_trace_read')
    if (Path(native.__file__).absolute() != STAGE / 'tools/fm1_sdk_prepare_stop_trace_read.py'
            or native.PROOF_SOURCE_SHA != PROOF_SHA or native.READ_SOURCE_SHA != READER_SHA):
        raise ValueError('Canonical distinct stop-trace source mismatch')
    for name, pin in zip(sources, (NATIVE_SHA, READER_SHA, PROOF_SHA)):
        if hashlib.sha256(read(STAGE / 'tools' / (name + '.py'))).hexdigest() != pin:
            raise ValueError('Source drift during canonical import')
    prepared = native.prepare_campaign(RUN / 'campaign.json')
    if (prepared.stop_sha256 != STOP_SHA or
            json.loads(prepared.seal)['preparation_stop_path'] != str(RUN / 'preparation-stop.json')):
        raise ValueError('Child stop envelope differs from canonical reader evidence')
    native.run_campaign(prepared)


if __name__ == '__main__':
    main()
