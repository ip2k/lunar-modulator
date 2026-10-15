"""Fail closed on stale, incomplete or changed native catalogue inputs."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/native'))
import build_application_probe as builder


def write_report(directory, report):
    (directory / 'report.json').write_text(json.dumps(report))


@pytest.mark.parametrize('shapes_voices', (8, 12))
@pytest.mark.parametrize('indexed_tft', (False, True), ids=('rgb565', 'indexed'))
@pytest.mark.parametrize('fault', range(16), ids=lambda i: f'receipt-{i:02d}')
def test_catalogue_receipt(tmp_path, monkeypatch, fault, indexed_tft, shapes_voices):
    # A bounded artificial catalogue isolates receipt checks from the compiler.
    monkeypatch.setattr(builder, 'source_manifest', lambda root: {'source.c': 'current'})
    expected = [f'c/engine-{i}.o' for i in range(16)]
    for shard, name in enumerate(expected):
        directory = tmp_path / f'shard-{shard:02d}'
        (directory / 'obj/c').mkdir(parents=True)
        (directory / 'cxx').mkdir()
        (directory / 'cxx/__config').write_bytes(b'config')
        (directory / 'obj' / name).write_bytes(b'bitcode')
        (directory / 'objects.json').write_text(json.dumps(expected))
        report = dict(shard=shard, chunks=16, catalogue_objects=16,
                      gpl_mods=1, modules='all', optimization='-Oz', lto=True,
                      shared_resampler=True, indexed_tft=indexed_tft, shapes_voices=shapes_voices, closed_sdk_archives=[], device_sdk_headers=[],
                      hot_dsp_ram=False,
                      engine_render_profile=False,
                      configured_sha256=hashlib.sha256(b'config').hexdigest(),
                      source_manifest={'source.c': 'current'},
                      results=[dict(index=shard, object=name, exit=0,
                                    sha256=hashlib.sha256(b'bitcode').hexdigest())])
        write_report(directory, report)
    with pytest.raises(SystemExit, match='Incompatible catalogue report'):
        builder.checked_catalogue(tmp_path, indexed_tft=not indexed_tft, shapes_voices=shapes_voices)
    with pytest.raises(SystemExit, match='Incompatible catalogue report'):
        builder.checked_catalogue(tmp_path, indexed_tft=indexed_tft,
                                  shapes_voices=12 if shapes_voices == 8 else 8)
    objects, receipts = builder.checked_catalogue(tmp_path, indexed_tft=indexed_tft, shapes_voices=shapes_voices)
    assert len(objects) == len(receipts) == 16
    directory = tmp_path / 'shard-00'
    report = json.loads((directory / 'report.json').read_text())
    if fault == 0: report['source_manifest'] = {'source.c': 'old'}
    elif fault == 1: del report['source_manifest']
    elif fault == 2: report['closed_sdk_archives'] = ['system.a']
    elif fault == 3: report['device_sdk_headers'] = ['uac_audio.h']
    elif fault == 4: report['lto'] = False
    elif fault == 5: report['results'][0]['sha256'] = 'wrong'
    elif fault == 6: report['results'][0]['exit'] = 1
    elif fault == 7: report['results'][0]['index'] = 16
    elif fault == 8: report['results'] = []
    elif fault == 9: report['results'] *= 2
    elif fault == 10: (directory / 'cxx/__config').write_bytes(b'changed')
    elif fault == 11: (directory / 'obj/c/engine-0.o').write_bytes(b'changed')
    elif fault == 12: report['shared_resampler'] = False
    elif fault == 13: report['optimization'] = '-Os'
    elif fault == 14: report['shard'] = 1
    else: (directory / 'objects.json').write_text(json.dumps(expected[::-1]))
    write_report(directory, report)
    with pytest.raises(SystemExit):
        builder.checked_catalogue(tmp_path, indexed_tft=indexed_tft, shapes_voices=shapes_voices)


def test_catalogue_hot_dsp_ram_receipt_is_explicit_and_matched(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, 'source_manifest', lambda root: {'source.c': 'current'})
    expected = [f'c/engine-{i}.o' for i in range(16)]
    for shard, name in enumerate(expected):
        directory = tmp_path / f'shard-{shard:02d}'
        (directory / 'obj/c').mkdir(parents=True)
        (directory / 'cxx').mkdir()
        (directory / 'cxx/__config').write_bytes(b'config')
        (directory / 'obj' / name).write_bytes(b'bitcode')
        (directory / 'objects.json').write_text(json.dumps(expected))
        report = dict(shard=shard, chunks=16, catalogue_objects=16,
                      gpl_mods=1, modules='all', optimization='-Oz', lto=True,
                      shared_resampler=True, indexed_tft=False, shapes_voices=12,
                      closed_sdk_archives=[], device_sdk_headers=[], hot_dsp_ram=False,
                      engine_render_profile=False,
                      configured_sha256=hashlib.sha256(b'config').hexdigest(),
                      source_manifest={'source.c': 'current'},
                      results=[dict(index=shard, object=name, exit=0,
                                    sha256=hashlib.sha256(b'bitcode').hexdigest())])
        write_report(directory, report)
    with pytest.raises(SystemExit, match='Incompatible catalogue report'):
        builder.checked_catalogue(tmp_path, hot_dsp_ram=True)
    for shard in range(16):
        path = tmp_path / f'shard-{shard:02d}/report.json'
        report = json.loads(path.read_text())
        del report['hot_dsp_ram']
        write_report(path.parent, report)
    with pytest.raises(SystemExit, match='Incompatible catalogue report'):
        builder.checked_catalogue(tmp_path)
    for shard in range(16):
        path = tmp_path / f'shard-{shard:02d}/report.json'
        report = json.loads(path.read_text())
        report['hot_dsp_ram'] = True
        write_report(path.parent, report)
    objects, receipts = builder.checked_catalogue(tmp_path, hot_dsp_ram=True)
    assert len(objects) == len(receipts) == 16
    with pytest.raises(SystemExit, match='Incompatible catalogue report'):
        builder.checked_catalogue(tmp_path, hot_dsp_ram=True, engine_render_profile=True)
    for shard in range(16):
        path = tmp_path / f'shard-{shard:02d}/report.json'
        report = json.loads(path.read_text())
        report['engine_render_profile'] = True
        write_report(path.parent, report)
    objects, receipts = builder.checked_catalogue(
        tmp_path, hot_dsp_ram=True, engine_render_profile=True)
    assert len(objects) == len(receipts) == 16
