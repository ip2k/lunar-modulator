"""One of sixteen fresh-ROM admission fault shards; no SG or device access."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import fm1_fresh_rom_backup as adapter


def main(shard, assets):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.chmod(root, 0o700)
        c = dict(schema=1, kind=adapter.KIND,
                 adapter_sha256=hashlib.sha256(Path(adapter.__file__).read_bytes()).hexdigest(),
                 observed_at=100, usb_binding=dict(path='1-1', busnum='1', devnum='27', vid='4c4a', pid='8057'),
                 loader_path=str(assets/'loader.bin'), profile_path=str(assets/'profile.json'),
                 profile_source_path=str(assets/'loader_config_profile.py'), receipt_path=str(root/'receipt'))
        mapping = dict(node='/dev/sg0', simulated=True)
        path = root/'campaign.json'
        path.write_text(json.dumps(c))
        real_load = adapter.load_source
        with patch('time.time', return_value=110), patch.object(adapter, 'load_source') as load:
            # Returned modules are private instances; replace only passive sysfs
            # discovery. No constructor, ioctl or descriptor open is invoked.
            def mocked(*args):
                module = real_load(*args)
                if args[0].name == 'fm1_fixed_loader_backup.py':
                    module.discover_sg = lambda usb: mapping
                return module
            load.side_effect = mocked
            bridge, p, got, marker = adapter.prepare(path)
            assert got == mapping and len(p.operations) == 8757
            assert p.operations[0].label == 'inquiry'
            assert bridge.inventory_digest(p.operations) == 'f99b6e738d19d24442ad4d056985e6f4dc200d0b09059b80428f4ff989838017'
            assert all(int.from_bytes(o.cdb[:2], 'big') in (0x1200,0xFB06,0xFB08,0xFC14,0xFC0A,0xFD05) for o in p.operations)
            bad = copy.deepcopy(c)
            if shard == 0: bad['schema'] = True
            elif shard == 1: bad['kind'] = 'other'
            elif shard == 2: bad['observed_at'] = -11
            elif shard == 3: bad['observed_at'] = 111
            elif shard == 4: bad['observed_at'] = True
            elif shard == 5: bad['observed_at'] = float('nan')
            elif shard == 6: bad['observed_at'] = float('inf')
            elif shard == 7: bad['unexpected'] = 1
            elif shard == 8: del bad['kind']
            elif shard == 9: bad['adapter_sha256'] = '0'*64
            elif shard == 10: bad['usb_binding']['pid'] = 'c755'
            elif shard == 11: bad['usb_binding']['path'] = '3-1'
            elif shard == 12: bad['loader_path'] = str(path)
            elif shard == 13: bad['profile_path'] = str(path)
            elif shard == 14: bad['profile_source_path'] = str(path)
            elif shard == 15: marker.write_text('consumed')
            else: raise ValueError('shard 0..15 required')
            path.write_text(json.dumps(bad))
            try: adapter.prepare(path)
            except (ValueError, OSError): pass
            else: raise AssertionError('Fault admitted')
            # Receipt/campaign renaming cannot erase enumeration consumption.
            if shard == 15:
                c['receipt_path'] = str(root/'another-receipt')
                path.write_text(json.dumps(c))
                try: adapter.prepare(path)
                except ValueError: pass
                else: raise AssertionError('Enumeration retry admitted')
    print(json.dumps(dict(shard=shard, passed=True, simulated=True, hardware_operations=0)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--shard', type=int, required=True)
    parser.add_argument('--assets', type=Path, required=True)
    args = parser.parse_args()
    main(args.shard, args.assets.absolute())
