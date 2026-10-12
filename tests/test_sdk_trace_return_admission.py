"""MIT. Closed admission mechanics, no fabricated lineage/factory acceptance."""
import ast
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import fm1_sdk_trace_return_admission as a


@pytest.mark.parametrize('missing', ['BOOT_SHA','READER_SHA','NATIVE_SHA','WIRE_SHA'])
def test_each_pending_literal_closes_before_any_read_or_import(monkeypatch,missing):
    for name in ('BOOT_SHA','READER_SHA','NATIVE_SHA','WIRE_SHA'):
        monkeypatch.setattr(a,name,None if name==missing else '0'*64)
    monkeypatch.setattr(a,'read_file',lambda *args:pytest.fail('Closed gate read evidence'))
    monkeypatch.setattr(a.importlib,'import_module',lambda *args:pytest.fail('Closed gate imported code'))
    with pytest.raises(ValueError,match='Closed'):
        a.validate_returned_state('/never-read')


@pytest.mark.parametrize('value',[None,True,0,'x'*64,'A'*64,'0'*63,'0'*65])
def test_activation_pin_is_exact_lowercase_sha(value):
    with pytest.raises(ValueError):a.pin(value)


def bound(template,values):
    tree=ast.parse(template)
    for n in tree.body:
        if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
            name=n.targets[0].id
            if name in values:
                value=values[name]
                n.value=ast.parse('Path('+repr(str(value))+')' if isinstance(value,Path) else repr(value),mode='eval').body
    return ast.unparse(ast.fix_missing_locations(tree)).encode()


@pytest.fixture(params=['wrapper','child'])
def derivative(request):
    root=Path(a.__file__).parent
    name='fm1_sdk_trace_capture.py' if request.param=='wrapper' else 'fm1_sdk_trace_capture_child.py'
    source=(root/name).read_bytes()
    pin=a.CAPTURE_SHA if request.param=='wrapper' else a.CHILD_SHA
    assert hashlib.sha256(source).hexdigest()==pin
    fields=a._WRAPPER_FIELDS if request.param=='wrapper' else a._CHILD_FIELDS
    values={n:'0'*64 for n in fields}
    values.update(STAGE=Path('/private/stage'),RUN=Path('/private/stage/read'))
    if request.param=='wrapper':values['PACKET_MEMBERS']=7
    return source,values


def test_real_tracked_template_allows_only_exact_literal_derivative(derivative):
    source,values=derivative
    a.verify_derivative(source,bound(source,values),values)


@pytest.mark.parametrize('fault',['body','extra','wrong-pin','wrong-path','missing','duplicate','expression'])
def test_real_template_derivative_rejects_executable_or_assignment_drift(derivative,fault):
    source,values=derivative;actual=bound(source,values)
    if fault=='body':actual=actual.replace(b'raise ValueError',b'raise RuntimeError',1)
    elif fault=='extra':actual+=b'\nprint("unreviewed")\n'
    elif fault=='wrong-pin':actual=actual.replace(b'0'*64,b'1'*64,1)
    elif fault=='wrong-path':actual=actual.replace(b'/private/stage',b'/foreign/stage',1)
    elif fault=='missing':values=dict(values);values.pop('RUN')
    elif fault=='duplicate':actual+=b'\nRUN = Path("/private/stage/read")\n'
    else:actual=actual.replace(b"Path('/private/stage')",b"Path('/private') / 'stage'",1)
    with pytest.raises(ValueError):a.verify_derivative(source,actual,values)


@pytest.mark.parametrize('name',['result.json','.result.json.pending','native.jsonl',
                                 'wrapper-stopped-ambiguous.json','wrapper-cleanup-ambiguous.json'])
def test_negative_evidence_survives_late_artifact_appearance(tmp_path,name):
    frozen=a.FrozenFiles();path=tmp_path/name
    assert frozen.optional(path) is None
    frozen.check();path.write_bytes(b'late')
    with pytest.raises(ValueError,match='absent'):frozen.check()


@pytest.mark.parametrize('fault',['bytes','symlink','missing','oversize'])
def test_positive_evidence_is_rechecked_and_not_replaced_by_inode_alias(tmp_path,fault):
    path=tmp_path/'evidence';path.write_bytes(b'original')
    frozen=a.FrozenFiles();assert frozen.freeze(path,limit=8)==b'original'
    if fault=='bytes':path.write_bytes(b'drift')
    elif fault=='symlink':
        path.unlink();other=tmp_path/'other';other.write_bytes(b'original');path.symlink_to(other)
    elif fault=='missing':path.unlink()
    else:path.write_bytes(b'x'*9)
    with pytest.raises((ValueError,OSError)):frozen.check()


@pytest.mark.parametrize('kind',['fifo','directory','symlink','relative'])
def test_bounded_nonblocking_direct_reader_rejects_nonregular(tmp_path,kind):
    path=tmp_path/kind
    if kind=='fifo':os.mkfifo(path)
    elif kind=='directory':path.mkdir()
    elif kind=='symlink':
        target=tmp_path/'source';target.write_bytes(b'private');path.symlink_to(target)
    else:path=Path('relative')
    with pytest.raises((ValueError,OSError)):a.read_file(path)


def test_private_directory_requires_direct_700(tmp_path):
    private=tmp_path/'private';private.mkdir(mode=0o700)
    assert a.private_directory(private)==private
    link=tmp_path/'alias';link.symlink_to(private)
    with pytest.raises(ValueError):a.private_directory(link)
    private.chmod(0o755)
    with pytest.raises(ValueError):a.private_directory(private)


def proof(lineage=None,evidence=(),absent=()):
    return a.ReturnedProof(b'{}','0'*64,b'{}','1'*64,'/private',evidence,(),
        '2'*64,'3'*64,100,'completed',absent,lineage)


def test_handmade_or_copied_proof_is_not_factory_authority():
    obj=proof()
    for copied in (obj,replace(obj)):
        with pytest.raises(ValueError,match='replay-created'):copied.check()


def test_registered_check_mechanics_keep_lineage_and_absence(monkeypatch,tmp_path):
    """Manufactured registry entry tests check only; not genuine factory proof."""
    calls=[];lineage=SimpleNamespace(check=lambda:calls.append('lineage'))
    absent=tmp_path/'result.json';obj=proof(lineage,absent=(absent,));a._AUTHORIZED.add(obj)
    obj.check();assert calls==['lineage']
    absent.write_bytes(b'late')
    with pytest.raises(ValueError,match='absent'):obj.check()
    with pytest.raises(ValueError,match='replay-created'):replace(obj).check()


def test_exact_source_loader_rejects_hash_before_executing(tmp_path):
    path=tmp_path/'untrusted.py';path.write_text('raise AssertionError("must not execute")\n')
    with pytest.raises(ValueError,match='source changed'):a.load_source(path,'0'*64,'_never_import')


def test_source_loader_detects_post_compile_source_drift(tmp_path,monkeypatch):
    path=tmp_path/'source.py';raw=b'VALUE=1\n';path.write_bytes(raw)
    original=a.read_file;calls=[]
    def read(actual,*args):
        calls.append(actual)
        return original(actual,*args) if len(calls)==1 else b'drift'
    monkeypatch.setattr(a,'read_file',read)
    with pytest.raises(ValueError,match='drift'):a.load_source(path,a.digest(raw),'_drift_import')
