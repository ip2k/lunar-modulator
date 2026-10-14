#!/usr/bin/env python3
"""Make a distinct build-input snapshot with only its packed project changed."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

source, payload, destination = map(Path, sys.argv[1:4])
if destination.exists():
    raise SystemExit('destination exists')
shutil.copytree(source, destination, symlinks=True)
data = payload.read_bytes()
profile = destination / 'profile.json'
manifest = json.loads(profile.read_text())
if len(manifest.get('content', [])) != 1 or manifest['content'][0].get('packed') != 'content-00.bin':
    raise SystemExit('expected a one-content prepared profile')
(destination / 'content-00.bin').write_bytes(data)
asset = manifest['content'][0]
asset['packed_sha256'] = hashlib.sha256(data).hexdigest()
asset['bytes'] = len(data)
manifest['packed_content_bytes'] = len(data)
profile.write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({
    'profile_sha256': hashlib.sha256(profile.read_bytes()).hexdigest(),
    'content_sha256': asset['packed_sha256'],
    'content_bytes': asset['bytes'],
    'source_sha256': asset['source_sha256'],
    'module_header_sha256': manifest['module_selection']['header_sha256'],
}, indent=2))
