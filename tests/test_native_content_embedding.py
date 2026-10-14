"""Selected content survives C compilation byte-for-byte without RAM globals."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/native'))
from embed_image_content import embed, content_source, MAX_PACKED_FILE
from prepare_image_profile import prepare, sha
from verify_image_profile import load_prepared_profile


@pytest.mark.parametrize('count', [0, 1, 2, 4])
@pytest.mark.parametrize('binary', [False, True], ids=['text-input', 'binary-input'])
@pytest.mark.parametrize('opt', ['-Os', '-Oz'])
def test_compiled_content(tmp_path, count, binary, opt):
    content = []
    for index in range(count):
        is_set = bool(index % 2)
        fixture = ('orbit.set.lunarb' if binary else 'orbit.set.movy1') if is_set else (
            'first-orbit.lunarb' if binary else 'first-orbit.lunar')
        name = f'asset-{index:02d}'
        shutil.copy(ROOT / 'tests/fixtures/state/1.0' / fixture, tmp_path / name)
        content.append(name)
    profile = tmp_path / 'input.json'
    profile.write_text(json.dumps(dict(version=1,
        engines=['trio', 'drums', 'shapes', 'macro', 'dx7'],
        effects=['filter', 'drive', 'echo', 'hall', 'limit'], midi=['arp'],
        modulation=['lfo', 'env', 'chance'], content=content)))
    prepared, output = tmp_path / 'prepared', tmp_path / 'embedded'
    prepare(profile, Path(os.environ['FM1_STATE_TOOL']), prepared)
    digest = sha((prepared / 'profile.json').read_bytes())
    inputs = load_prepared_profile(prepared, digest)
    report = embed(prepared, digest, output)
    assert report['asset_count'] == count
    assert report['packed_content_bytes'] == sum(map(len, inputs.packed_content))
    assert all(report[k] is False for k in ('installable', 'native_link_verified',
               'native_ram_verified', 'hardware_tested', 'sequence_semantics_verified'))
    source = output / 'content_catalogue.c'
    assert sha(source.read_bytes()) == report['source_sha256']
    assert (output / 'fm1_modules.h').read_bytes() == inputs.module_header
    # The emitted data no longer depends on the prepared files remaining present.
    shutil.rmtree(prepared)
    assert source.read_bytes() == content_source(inputs)
    probe = tmp_path / 'probe.c'
    probe.write_text('''#include <stdio.h>
#include "content_catalogue.h"
int main(void) {
    unsigned i;
    printf("%u\\n", (unsigned)lunar_content_count);
    for (i = 0; i < lunar_content_count; ++i) {
        const lunar_content_asset_t *a = &lunar_content_catalogue[i];
        printf("%u %u\\n", (unsigned)a->kind, (unsigned)a->size);
        if (fwrite(a->bytes, 1, a->size, stdout) != a->size) return 1;
    }
    return 0;
}
''')
    includes = [ROOT / 'firmware/native', ROOT / 'engines/state', ROOT / 'engines/include']
    inc_flags = [arg for p in includes for arg in ('-I', str(p))]
    executable = tmp_path / 'probe'
    subprocess.run(['cc', '-std=c99', opt, *inc_flags, str(source), str(probe),
                    '-o', str(executable)], check=True, capture_output=True)
    expected = f'{count}\n'.encode()
    for asset, payload in zip(inputs.report['content'], inputs.packed_content):
        kind = {'project': 1, 'set': 7}[asset['kind']]
        expected += f'{kind} {len(payload)}\n'.encode() + payload
    assert subprocess.check_output([str(executable)]) == expected
    tc = Path(os.environ['FM1_NATIVE_TOOLCHAIN'])
    obj = tmp_path / 'content.o'
    subprocess.run([str(tc / 'common/bin/clang'), '-target', 'pi32v2', '-mcpu=r3',
                    '-mfprev1', '-std=c99', opt, '-ffreestanding', '-fno-builtin',
                    '-ffunction-sections', '-fdata-sections', *inc_flags,
                    '-isystem', str(tc / 'pi32v2/include'), '-c', str(source),
                    '-o', str(obj)], check=True, capture_output=True)
    assert not subprocess.check_output([str(tc / 'pi32v2/bin/nm'), '-u', str(obj)]).strip()
    sections = subprocess.check_output([str(tc / 'common/bin/objdump'), '-h', str(obj)], text=True)
    sizes = {m[1]: int(m[2], 16) for m in re.finditer(
        r'^[ \t]*\d+[ \t]+(\.[^ \t\n]+)[ \t]+([0-9a-f]+)[ \t]+[0-9a-f]+', sections, re.M)}
    assert not sum(v for k, v in sizes.items() if k.startswith(('.data', '.bss', '.sdata', '.sbss')))
    for index, payload in enumerate(inputs.packed_content):
        assert sizes[f'.rodata.lunar_content_{index:02d}'] == len(payload)
    assert sizes['.rodata.lunar_content_count'] == 4
    assert sizes['.rodata.lunar_content_catalogue'] == 12 * max(1, count)


def test_content_refusal_has_no_output(tmp_path):
    with pytest.raises(ValueError, match='lowercase SHA256'):
        embed(tmp_path / 'absent', 'bad-digest', tmp_path / 'output')
    assert not (tmp_path / 'output').exists()


@pytest.mark.parametrize('length', [0, 31, MAX_PACKED_FILE + 1])
def test_embedded_container_bound(length):
    from verify_image_profile import PreparedInputs
    inputs = PreparedInputs(dict(content=[dict(kind='project')]), b'', (b'x' * length,))
    with pytest.raises(ValueError, match='container bounds'):
        content_source(inputs)


@pytest.mark.parametrize('fixture', ['first-orbit.lunarb', 'orbit.set.lunarb'])
def test_corrupt_binary_input_has_no_accepted_manifest(tmp_path, fixture):
    payload = bytearray((ROOT / 'tests/fixtures/state/1.0' / fixture).read_bytes())
    payload[-1] ^= 1
    (tmp_path / 'corrupt.bin').write_bytes(payload)
    profile = tmp_path / 'input.json'
    profile.write_text(json.dumps(dict(version=1, engines=['trio'], content=['corrupt.bin'])))
    output = tmp_path / 'prepared'
    with pytest.raises(ValueError, match='State tool rejected content'):
        prepare(profile, Path(os.environ['FM1_STATE_TOOL']), output)
    assert not (output / 'profile.json').exists()


def test_content_descriptor_count_mismatch():
    from verify_image_profile import PreparedInputs
    with pytest.raises(ValueError, match='differ in count'):
        content_source(PreparedInputs(dict(content=[]), b'', (b'x' * 32,)))


@pytest.mark.parametrize('options,message', [
    (['--startup-set-index', '0'], 'requires --link-set-loader'),
    (['--startup-project-index', '0'], 'requires --link-project-loader'),
    (['--startup-project-index', '0', '--startup-set-index', '0'], 'requires --link-set-loader'),
    (['--prepared-profile', 'absent'], 'require each other'),
    (['--expected-profile-sha256', '0' * 64], 'require each other'),
    (['--prepared-profile', 'absent', '--expected-profile-sha256', '0' * 64,
      '--modules', 'trio'], 'cannot be combined'),
    (['--prepared-profile', 'absent', '--expected-profile-sha256', '0' * 64,
      '--exclude', 'dx7'], 'cannot be combined'),
])
def test_linker_profile_option_refusal(tmp_path, options, message):
    output = tmp_path / 'linked'
    result = subprocess.run([sys.executable, str(ROOT / 'tools/native/build_application_probe.py'),
        '--toolchain', 'unused', '--catalogue', 'unused', '--build', str(output),
        *options], capture_output=True, text=True)
    assert result.returncode == 2 and message in result.stderr
    assert not output.exists()


def test_linker_rejects_inconsistent_prepared_module_header(tmp_path):
    profile = tmp_path / 'input.json'
    profile.write_text(json.dumps(dict(version=1, engines=['trio'], content=[])))
    prepared = tmp_path / 'prepared'
    prepare(profile, Path(os.environ['FM1_STATE_TOOL']), prepared)
    # Internally consistent digests do not make a stale/different header match
    # the selected modules regenerated by the current canonical Make catalogue.
    header = prepared / 'fm1_modules.h'
    header.write_bytes(header.read_bytes() + b'\n#define UNEXPECTED_PROFILE_HEADER 1\n')
    manifest = prepared / 'profile.json'
    report = json.loads(manifest.read_text())
    report['module_selection']['header_sha256'] = sha(header.read_bytes())
    manifest.write_text(json.dumps(report))
    output = tmp_path / 'linked'
    result = subprocess.run([sys.executable, str(ROOT / 'tools/native/build_application_probe.py'),
        '--toolchain', 'unused', '--catalogue', 'unused', '--build', str(output),
        '--prepared-profile', str(prepared), '--expected-profile-sha256', sha(manifest.read_bytes())],
        capture_output=True, text=True)
    assert result.returncode == 2 and 'differs from current module selection' in result.stderr
    assert not (output / 'verification.json').exists()
    assert not (output / 'lunar-app-probe.elf').exists()


@pytest.mark.parametrize('index,loader,message', [
    (-1, True, 'outside the embedded catalogue'),
    (2, True, 'outside the embedded catalogue'),
    (0, True, 'must identify a SET'),
    (1, False, 'requires --link-set-loader'),
])
def test_startup_set_option_refusal(tmp_path, index, loader, message):
    content = []
    for name in ('first-orbit.lunar', 'orbit.set.movy1'):
        shutil.copy(ROOT / 'tests/fixtures/state/1.0' / name, tmp_path / name)
        content.append(name)
    profile = tmp_path / 'input.json'
    profile.write_text(json.dumps(dict(version=1,
        engines=['trio', 'drums', 'shapes', 'macro', 'dx7'],
        effects=['filter', 'drive', 'echo', 'hall', 'limit'], midi=['arp'],
        modulation=['lfo', 'env', 'chance'], content=content)))
    prepared = tmp_path / 'prepared'
    prepare(profile, Path(os.environ['FM1_STATE_TOOL']), prepared)
    output = tmp_path / 'linked'
    options = ['--link-set-loader'] if loader else []
    result = subprocess.run([sys.executable, str(ROOT / 'tools/native/build_application_probe.py'),
        '--toolchain', 'unused', '--catalogue', 'unused', '--build', str(output),
        '--prepared-profile', str(prepared), '--expected-profile-sha256',
        sha((prepared / 'profile.json').read_bytes()), '--startup-set-index', str(index),
        *options], capture_output=True, text=True)
    assert result.returncode == 2 and message in result.stderr
    assert not output.exists()
