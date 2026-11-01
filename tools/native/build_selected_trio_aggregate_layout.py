#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Link the fixed Trio interactive plus offline PROJECT layout offline.

This measures retained target storage and closure using the unqualified
return-candidate startup. It does not bind interactive hardware, admit live
PROJECT storage, package, install, execute, or qualify the target image.
"""
import argparse
import json
from pathlib import Path
import subprocess

from build_diagnostic import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--toolchain-archive', type=Path, required=True)
    parser.add_argument('--cxx-headers', type=Path, required=True)
    parser.add_argument('--renderer', type=Path, required=True)
    parser.add_argument('--state-tool', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--jobs', type=int, choices=range(1, 5), default=4)
    args = parser.parse_args()
    try:
        result = build(args, selected=True, return_candidate=True,
                       aggregate_layout=True)
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps({key: value for key, value in result.items()
                      if key in ('profile', 'hardware_admitted', 'elf_sha256', 'sizes')}))


if __name__ == '__main__':
    main()
