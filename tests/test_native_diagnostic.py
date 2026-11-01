"""Offline source-bound diagnostic builder guards; no toolchain or device needed."""
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tarfile
from types import SimpleNamespace
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_diagnostic', ROOT / 'tools/native/build_diagnostic.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_inventory_rejects_changed_source(tmp_path):
    source = tmp_path / 'unit.c'
    source.write_text('int value;\n')
    (tmp_path / 'inventory.json').write_text(json.dumps({'files': {'unit.c': builder.digest(source)}}))
    builder.check_inventory(tmp_path)
    source.write_text('int changed;\n')
    with pytest.raises(ValueError, match='source pin mismatch'):
        builder.check_inventory(tmp_path)


def test_current_input_manifest_and_vendor_pins():
    inputs = builder.manifest()
    for name in ['tools/native/build_diagnostic.py', 'tools/jieli/audit_link.py',
                 'firmware/native/diagnostic_api.h', 'sim/web/src/fm1_app.c',
                 'engines/mk/mod.mk']:
        assert inputs[name] == builder.digest(ROOT / name)
    assert not any('__pycache__' in p or p.endswith('.o') for p in inputs)
    for name in ['dinghy', 'compiler-rt', 'musl', 'printf']:
        builder.check_inventory(ROOT / 'firmware/third_party' / name)


@pytest.fixture
def pinned_tree(tmp_path, monkeypatch):
    """Synthetic input bytes are never executed and contain no vendor material."""
    source = tmp_path / 'archive-source'
    for name in ['common/bin/clang', 'common/bin/objdump',
                 'pi32v2/bin/ld', 'pi32v2/bin/nm', 'pi32v2/include/stdint.h']:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(('synthetic ' + name).encode())
        path.chmod(0o755 if '/bin/' in name else 0o644)
    (source / 'common/bin/clang++').symlink_to('clang')
    archive = tmp_path / 'toolchain.tar.xz'
    with tarfile.open(archive, 'w:xz') as contents:
        contents.add(source, arcname='synthetic-toolchain')
    actual = tmp_path / 'actual-toolchain'
    shutil.copytree(source, actual, symlinks=True)
    monkeypatch.setattr(builder, 'TOOLCHAIN_SHA256', builder.digest(archive))
    return actual, archive


def test_matching_extracted_toolchain_has_bound_receipt(pinned_tree):
    tree, archive = pinned_tree
    binding = builder.bind_toolchain(tree, archive)
    assert binding['schema'] == 1
    assert binding['archive_sha256'] == builder.digest(archive)
    assert binding['archive_root'] == 'synthetic-toolchain'
    assert len(binding['tree_sha256']) == 64
    assert binding['tree_manifest'] == builder.toolchain_tree(tree)
    assert binding['tree_manifest']['common/bin/clang']['execute_bits'] == 0o111
    assert binding['tree_manifest']['common/bin/clang++'] == dict(kind='symlink', target='clang')
    assert binding == builder.bind_toolchain(tree, archive)


@pytest.mark.parametrize('name', ['common/bin/clang', 'common/bin/objdump',
    'pi32v2/bin/ld', 'pi32v2/bin/nm', 'pi32v2/include/stdint.h'])
def test_unrelated_executable_or_target_header_refused_before_build(
        pinned_tree, tmp_path, monkeypatch, name):
    tree, archive = pinned_tree
    (tree / name).write_bytes(b'unrelated input with a perfectly pinned archive')
    out = tmp_path / 'must-not-be-created'
    def forbidden(*args, **kwargs):
        pytest.fail('provenance refusal must precede inventories and subprocesses')
    monkeypatch.setattr(builder, 'check_inventory', forbidden)
    monkeypatch.setattr(builder.subprocess, 'run', forbidden)
    args = SimpleNamespace(toolchain=tree, toolchain_archive=archive,
                           out=out, cxx_headers=tmp_path / 'unused-headers', jobs=1)
    with pytest.raises(ValueError, match='tree differs from pinned archive'):
        builder.build(args)
    assert not out.exists()


@pytest.mark.parametrize('change', ['extra', 'missing', 'executable-bit', 'link-target'])
def test_extracted_tree_identity_must_match_archive(pinned_tree, change):
    tree, archive = pinned_tree
    if change == 'extra':
        (tree / 'pi32v2/include/injected.h').write_text('injected')
    elif change == 'missing':
        (tree / 'pi32v2/include/stdint.h').unlink()
    elif change == 'executable-bit':
        (tree / 'common/bin/clang').chmod(0o644)
    else:
        (tree / 'common/bin/clang++').unlink()
        (tree / 'common/bin/clang++').symlink_to('objdump')
    with pytest.raises(ValueError, match='tree differs from pinned archive'):
        builder.bind_toolchain(tree, archive)


def test_escaping_toolchain_link_refused(pinned_tree, tmp_path):
    tree, archive = pinned_tree
    outside = tmp_path / 'outside'
    outside.write_text('unbound target')
    (tree / 'common/bin/clang++').unlink()
    (tree / 'common/bin/clang++').symlink_to(outside)
    with pytest.raises(ValueError, match='link escapes tree'):
        builder.bind_toolchain(tree, archive)


def test_wrong_archive_pin_refused(pinned_tree, monkeypatch):
    tree, archive = pinned_tree
    monkeypatch.setattr(builder, 'TOOLCHAIN_SHA256', '0' * 64)
    with pytest.raises(ValueError, match='archive differs from pinned source'):
        builder.bind_toolchain(tree, archive)


@pytest.mark.parametrize('kind', ['traversal', 'absolute', 'duplicate', 'multiple-roots',
                                  'fifo', 'hardlink-escape', 'hardlink-cycle', 'link-ancestor'])
def test_unsafe_archive_refused_without_extraction(pinned_tree, monkeypatch, kind):
    tree, archive = pinned_tree
    def file(contents, name, payload=b'synthetic'):
        member = tarfile.TarInfo(name)
        member.size = len(payload)
        contents.addfile(member, io.BytesIO(payload))
    with tarfile.open(archive, 'w:xz') as contents:
        if kind == 'traversal':
            file(contents, 'synthetic/../escape')
        elif kind == 'absolute':
            file(contents, '/absolute/escape')
        elif kind == 'duplicate':
            file(contents, 'synthetic/a'); file(contents, 'synthetic/a')
        elif kind == 'multiple-roots':
            file(contents, 'synthetic/a'); file(contents, 'other/a')
        elif kind == 'fifo':
            member = tarfile.TarInfo('synthetic/pipe'); member.type = tarfile.FIFOTYPE
            contents.addfile(member)
        elif kind in ['hardlink-escape', 'hardlink-cycle']:
            member = tarfile.TarInfo('synthetic/link'); member.type = tarfile.LNKTYPE
            member.linkname = '../outside' if kind == 'hardlink-escape' else 'synthetic/link'
            contents.addfile(member)
        else:
            member = tarfile.TarInfo('synthetic/link'); member.type = tarfile.SYMTYPE
            member.linkname = 'common'; contents.addfile(member)
            file(contents, 'synthetic/link/child')
    monkeypatch.setattr(builder, 'TOOLCHAIN_SHA256', builder.digest(archive))
    with pytest.raises(ValueError):
        builder.bind_toolchain(tree, archive)
    assert not (tree.parent / 'escape').exists()


def test_regular_archive_hardlinks_match_extracted_bytes(pinned_tree, monkeypatch):
    tree, archive = pinned_tree
    (tree / 'duplicate').write_bytes((tree / 'common/bin/clang').read_bytes())
    (tree / 'duplicate').chmod(0o755)
    with tarfile.open(archive, 'w:xz') as contents:
        for path in sorted(tree.rglob('*')):
            if path.name != 'duplicate':
                contents.add(path, arcname='synthetic/' + path.relative_to(tree).as_posix(), recursive=False)
        member = tarfile.TarInfo('synthetic/duplicate')
        member.type = tarfile.LNKTYPE
        member.linkname = 'synthetic/common/bin/clang'
        contents.addfile(member)
    monkeypatch.setattr(builder, 'TOOLCHAIN_SHA256', builder.digest(archive))
    binding = builder.bind_toolchain(tree, archive)
    assert binding['tree_manifest']['duplicate'] == binding['tree_manifest']['common/bin/clang']


def test_post_build_snapshot_detects_input_mutation(pinned_tree):
    tree, archive = pinned_tree
    binding = builder.bind_toolchain(tree, archive)
    (tree / 'pi32v2/include/stdint.h').write_text('changed after verification')
    assert builder.toolchain_tree(tree) != binding['tree_manifest']
