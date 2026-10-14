"""Mock-only generic read-bound reset policy and one-shot lifecycle tests."""
import ctypes
from pathlib import Path
import stat
import sys
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import fm1_event120_generic_rom_backup as read
import fm1_uboot_read as reader
from native import event120_generic_boot as boot
from native import event120_reset as completion


def usb(devnum="55"):
    return {"path":"1-1", "busnum":"1", "devnum":devnum, "vid":"4c4a", "pid":"8057"}


def campaign():
    return {
        "schema":1, "kind":boot.KIND, "adapter_sha256":"a"*64,
        "read_manifest_path":"/private/manifest.json", "read_manifest_sha256":"b"*64,
        "read_commands_sha256":"c"*64, "read_campaign_sha256":"d"*64,
        "snapshot_path":"/private/boot-snapshot.json", "snapshot_sha256":"e"*64,
        "snapshot_observed_at":1000, "usb_binding":usb(), "sg_binding":{},
        "active_session_state":boot.ACTIVE_SESSION, "receipt_path":"/private/boot",
        "expected_current_flash_sha256":"f"*64,
    }


def test_boot_campaign_requires_external_digest_and_explicit_usb55():
    raw=boot.canonical(campaign())
    assert boot.validate_boot_campaign(raw,boot.digest(raw),"55")["usb_binding"] == usb()
    with pytest.raises(ValueError,match="externally pinned"):
        boot.validate_boot_campaign(raw,"0"*64,"55")
    with pytest.raises(ValueError,match="Explicit expected USB"):
        boot.validate_boot_campaign(raw,boot.digest(raw),"54")
    for changed in (dict(campaign(),usb_binding=usb("54")),
                    dict(campaign(),schema=True),
                    dict(campaign(),unknown=True),
                    dict(campaign(),no_later_commands_attested=True),
                    dict(campaign(),expected_current_flash_sha256="z"*64)):
        raw=boot.canonical(changed)
        with pytest.raises(ValueError):
            boot.validate_boot_campaign(raw,boot.digest(raw),"55")


def _fake_session(monkeypatch, *, ioctl_fault=None):
    mapping={"node":"/dev/sg-test","node_identity":[1,2,3],"usb_binding":usb()}
    bridge=SimpleNamespace(discover_sg=lambda _usb:mapping)
    underlying=SimpleNamespace(check=lambda:None)
    now=time.time()
    prepared=boot.Prepared(campaign=boot.canonical(dict(campaign(),usb_binding=usb())),
        campaign_sha256="a"*64,expected_mapping=boot.canonical(mapping),
        target_prepared=underlying,bridge=bridge,header_type=reader.SGHeader,
        evidence=(),snapshot_observed_at=now,boot_marker=Path("/unused"))
    boot._AUTHORIZED.add(prepared)
    opened=[];closed=[];ioctls=[];events=[]
    monkeypatch.setattr(boot,"_live_mapping",lambda _bridge,_usb:mapping)
    monkeypatch.setattr(boot.os,"open",lambda path,*args:opened.append(path) or 73)
    monkeypatch.setattr(boot.os,"close",lambda fd:closed.append(fd))
    monkeypatch.setattr(boot.fcntl,"flock",lambda *args:None)
    monkeypatch.setattr(boot.os,"fstat",lambda fd:SimpleNamespace(st_mode=stat.S_IFCHR,st_dev=1,st_ino=2,st_rdev=3))
    def ioctl(fd,request,header):
        ioctls.append((fd,request));ctypes.memmove(header.data,boot.RESET_CDB,2)
        if ioctl_fault == "status": header.host=7
    monkeypatch.setattr(completion.fcntl,"ioctl",ioctl)
    session=boot.session_class(completion)(prepared,lambda event,**fields:events.append((event,fields)))
    return session,opened,closed,ioctls,events


def test_reset_adapter_is_generic_and_sends_once_without_boot_claim(monkeypatch):
    assert boot.READ_KIND == read.KIND
    assert boot.READ_ADAPTER_SHA == read.digest(Path(read.__file__).read_bytes())
    session,opened,closed,ioctls,events=_fake_session(monkeypatch)
    result=session.request_reset()
    assert opened == ["/dev/sg-test"]
    assert len(ioctls)==1 and ioctls[0][1]==0x2285
    assert result == {"request_completion":True,"core_reset_observed":False,"boot_observed":False}
    assert [event for event,_ in events] == ["reset_submit_intent","reset_sg_completion"]
    assert session.fd is None and closed == [73]
    with pytest.raises(ValueError): session.request_reset()
    assert len(ioctls)==1


def test_ambiguous_reply_latches_failure_and_does_not_retry(monkeypatch):
    session,opened,closed,ioctls,events=_fake_session(monkeypatch,ioctl_fault="status")
    with pytest.raises(OSError,match="incomplete or ambiguous"):
        session.request_reset()
    assert opened == ["/dev/sg-test"] and len(ioctls)==1
    assert session.fd is None and session.failed and closed == [73]
    with pytest.raises(ValueError): session.request_reset()
    assert len(ioctls)==1


def _synthetic_read_bundle(root, monkeypatch):
    """Create a complete synthetic transcript; no SG descriptor or device is opened."""
    import hashlib
    import json
    import types

    root.mkdir(mode=0o700)
    root.chmod(0o700)
    read_started=time.time()-2
    usb_binding=usb("55")
    mapping={"node":"/dev/sg-test","class":"/sys/class/scsi_generic/sg-test",
        "device":"/sys/devices/test/host0/target0:0:0/0:0:0:0","usb":"/sys/devices/test/usb1/1-1",
        "node_identity":[1,2,3],"class_identity":[4,5,0],"device_identity":[6,7,0],"usb_identity":[8,9,0]}
    read_dir=root/"read";read_dir.mkdir(mode=0o700);read_dir.chmod(0o700)
    read_adapter_path=Path(read.__file__).resolve()
    read_adapter_sha=read.digest(read_adapter_path.read_bytes())
    target_data=b"synthetic-current-flash".ljust(1048576,b"X")
    target_sha=read.digest(target_data)
    snapshot_path=root/"read-snapshot.json"
    snapshot_raw=read.canonical({"schema":1,"kind":read.SNAPSHOT_KIND,"observed_at":read_started-1,
        "usb_binding":usb_binding,"sg_binding":mapping})
    snapshot_path.write_bytes(snapshot_raw)
    read_campaign={"schema":1,"kind":read.KIND,"adapter_sha256":read_adapter_sha,
        "snapshot_path":str(snapshot_path),"snapshot_sha256":read.digest(snapshot_raw),
        "loader_path":"/private/loader.bin","profile_path":"/private/profile.json",
        "profile_source_path":"/private/profile.c","usb_binding":usb_binding,
        "receipt_path":str(read_dir),"expected_current_flash_sha256":target_sha}
    read_campaign_path=root/"read-campaign.json"
    read_campaign_raw=read.canonical(read_campaign);read_campaign_path.write_bytes(read_campaign_raw)
    operations=[SimpleNamespace(phase="read",label="synthetic",cdb=b"\x00"*16,payload=b"",read_size=0)
                for _ in range(8757)]
    inventory_sha=read.INVENTORY_SHA
    class Bridge:
        LOADER_SHA="fe6d1bd36c8ffe4674e4a05ee748fe87480b5867fac58230b14ff089d411012c"
        LOADER_SIZE=24064
        PROFILE_SHA="3c03e413b9df29d85e4c07d886d9bfb9b3ab2fc66845d5220f82998dd44f4afe"
        PROFILE_SOURCE_SHA="9664e1329d8259362da78c047ce2d6003dfe8df2850f02703f98e8b6bf277cd8"
        def pinned_file(self,path,expected):
            if expected==self.LOADER_SHA:return b"L"*self.LOADER_SIZE
            if expected==self.PROFILE_SHA:return read.canonical({"profile":1})
            return b"source"
        def discover_sg(self,usb):return mapping
        def inventory_digest(self,_ops):return read.INVENTORY_SHA
    bridge=Bridge()
    inventory=types.SimpleNamespace(inventory=lambda *args:operations,
        inventory_digest=lambda _ops:inventory_sha)
    original=boot.load_source
    def loader(path,expected,name):
        if name.endswith("_verify_bridge"):return bridge
        if name.endswith("_verify_reader"):return reader
        if name.endswith("_verify_inventory"):return inventory
        return original(path,expected,name)
    monkeypatch.setattr(boot,"load_source",loader)

    commands=[]
    def row(event,**fields):commands.append(json.dumps(dict(time=read_started,event=event,**fields),sort_keys=True,separators=(",",":")))
    row("generic_rom_read_prepared",campaign_sha256=read.digest(read_campaign_raw),
        adapter_sha256=read_adapter_sha,snapshot_sha256=read_campaign["snapshot_sha256"],
        usb_binding=usb_binding,sg_binding=mapping,loader_sha256=bridge.LOADER_SHA,
        profile_sha256=bridge.PROFILE_SHA,profile_source_sha256=bridge.PROFILE_SOURCE_SHA,
        reader_sha256=read.SOURCES["fm1_uboot_read.py"],commands=8757,
        request_inventory_sha256=inventory_sha,expected_current_flash_sha256=target_sha,
        flash_operations=0,reset_operations=0,upload_operations=47,install_history_proven=False,
        boot_observed=False,physical_recovery_verified=False,retry=False)
    for index,op in enumerate(operations):
        row("sg_submit_intent",index=index,phase=op.phase,label=op.label,cdb=op.cdb.hex(),
            payload_sha256=None,out_len=0,in_len=0,retry=False)
        row("sg_completion",index=index,status=0,masked=0,msg=0,host=0,driver=0,resid=0,
            info=0,sense_len=0,sense_hex="",retry=False)
    dumps=[{"file":name,"bytes":1048576,"sha256":target_sha,"complete":True}
           for name in ("dumpA.bin","dumpB.bin")]
    row("generic_rom_read_completed",identical=True,current_flash_sha256=target_sha,
        dumps=dumps,commands=8757,request_inventory_sha256=inventory_sha,
        flash_operations=0,reset_operations=0,install_history_proven=False,
        boot_observed=False,physical_recovery_verified=False,retry=False)
    commands_raw=("\n".join(commands)+"\n").encode()
    (read_dir/"commands.jsonl").write_bytes(commands_raw)
    for name in ("dumpA.bin","dumpB.bin"):(read_dir/name).write_bytes(target_data)
    marker=boot._rom_marker_path(root,usb_binding,mapping)
    marker.write_text(read.digest(read_campaign_raw))
    manifest={"schema":1,"kind":read.KIND,"campaign_path":str(read_campaign_path),
        "campaign_sha256":read.digest(read_campaign_raw),"adapter_sha256":read_adapter_sha,
        "source_sha256":read.SOURCES,"snapshot_path":str(snapshot_path),
        "snapshot_sha256":read_campaign["snapshot_sha256"],"usb_binding":usb_binding,
        "sg_binding":mapping,"loader_sha256":bridge.LOADER_SHA,
        "loader_profile_sha256":bridge.PROFILE_SHA,"profile_source_sha256":bridge.PROFILE_SOURCE_SHA,
        "reader_sha256":read.SOURCES["fm1_uboot_read.py"],"request_inventory_sha256":inventory_sha,
        "commands":8757,"flash_bytes":1048576,"expected_current_flash_sha256":target_sha,
        "current_flash_sha256":target_sha,"commands_sha256":read.digest(commands_raw),
        "dumps":dumps,"identical":True,"flash_operations":0,"reset_operations":0,
        "install_history_proven":False,"boot_observed":False,"physical_recovery_verified":False,
        "kernel_exclusivity":False}
    manifest_path=read_dir/"manifest.json";manifest_raw=read.canonical(manifest);manifest_path.write_bytes(manifest_raw)
    return {"root":root,"usb":usb_binding,"mapping":mapping,"target_sha":target_sha,
        "campaign_path":read_campaign_path,"campaign_raw":read_campaign_raw,
        "snapshot_path":snapshot_path,"snapshot_raw":snapshot_raw,"manifest_path":manifest_path,
        "manifest_raw":manifest_raw,"commands_sha":read.digest(commands_raw),"read_dir":read_dir,
        "completed_at":read_started}


def test_full_synthetic_read_bundle_binds_campaign_manifest_dumps_and_marker(tmp_path,monkeypatch):
    fixture=_synthetic_read_bundle(tmp_path/"evidence",monkeypatch)
    checked=boot.verify_read_bundle(fixture["manifest_path"],read.digest(fixture["manifest_raw"]),
        fixture["commands_sha"],campaign_sha256=read.digest(fixture["campaign_raw"]),
        expected_devnum="55",expected_flash_sha256=fixture["target_sha"],now=fixture["completed_at"])
    assert checked["manifest"]["commands"]==8757
    assert checked["manifest"]["dumps"][0]["sha256"]==fixture["target_sha"]
    with pytest.raises(ValueError,match="policy, identity or source"):
        boot.verify_read_bundle(fixture["manifest_path"],read.digest(fixture["manifest_raw"]),
            fixture["commands_sha"],campaign_sha256=read.digest(fixture["campaign_raw"]),
            expected_devnum="55",expected_flash_sha256="0"*64,now=fixture["completed_at"])
    with pytest.raises(ValueError,match="Pinned evidence hash differs"):
        boot.verify_read_bundle(fixture["manifest_path"],"0"*64,
            fixture["commands_sha"],campaign_sha256=read.digest(fixture["campaign_raw"]),
            expected_devnum="55",expected_flash_sha256=fixture["target_sha"],now=fixture["completed_at"])


def test_boot_prepare_chains_synthetic_read_and_rejects_sg_replacement(tmp_path,monkeypatch):
    fixture=_synthetic_read_bundle(tmp_path/"evidence",monkeypatch)
    root=fixture["root"]
    now=fixture["completed_at"]+1
    boot_snapshot={"schema":1,"kind":boot.BOOT_SNAPSHOT_KIND,"observed_at":now,
        "usb_binding":fixture["usb"],"sg_binding":fixture["mapping"]}
    snapshot_path=root/"boot-snapshot.json";snapshot_raw=read.canonical(boot_snapshot)
    snapshot_path.write_bytes(snapshot_raw)
    output=root/"boot-output"
    campaign_value={"schema":1,"kind":boot.KIND,
        "adapter_sha256":read.digest(Path(boot.__file__).read_bytes()),
        "read_manifest_path":str(fixture["manifest_path"]),
        "read_manifest_sha256":read.digest(fixture["manifest_raw"]),
        "read_commands_sha256":fixture["commands_sha"],
        "read_campaign_sha256":read.digest(fixture["campaign_raw"]),
        "snapshot_path":str(snapshot_path),"snapshot_sha256":read.digest(snapshot_raw),
        "snapshot_observed_at":now,"usb_binding":fixture["usb"],"sg_binding":fixture["mapping"],
        "active_session_state":boot.ACTIVE_SESSION,"receipt_path":str(output),
        "expected_current_flash_sha256":fixture["target_sha"]}
    campaign_path=root/"boot-campaign.json";campaign_raw=read.canonical(campaign_value);campaign_path.write_bytes(campaign_raw)
    class Underlying:
        def __init__(self,*args):pass
        def check(self):return None
    target=SimpleNamespace(Prepared=Underlying,_AUTHORIZED=set())
    monkeypatch.setattr(boot,"_target_modules",lambda _root:(target,completion))
    monkeypatch.setattr(boot,"_live_mapping",lambda _bridge,_usb:fixture["mapping"])
    prepared,completion_loaded=boot.prepare(campaign_path,campaign_sha256=read.digest(campaign_raw),
        expected_devnum="55",now=now)
    assert prepared in boot._AUTHORIZED and completion_loaded is completion
    assert not output.exists()

    # A fresh snapshot and campaign that agree with each other still cannot
    # replace the SG mapping bound by the completed read.
    changed_mapping=dict(fixture["mapping"],node_identity=[9,9,9])
    changed_snapshot=dict(boot_snapshot,sg_binding=changed_mapping)
    changed_snapshot_path=root/"replacement-snapshot.json"
    changed_snapshot_raw=read.canonical(changed_snapshot)
    changed_snapshot_path.write_bytes(changed_snapshot_raw)
    changed=dict(campaign_value,sg_binding=changed_mapping,
        snapshot_path=str(changed_snapshot_path),snapshot_sha256=read.digest(changed_snapshot_raw),
        snapshot_observed_at=now)
    changed_path=root/"changed-boot-campaign.json";changed_raw=read.canonical(changed);changed_path.write_bytes(changed_raw)
    with pytest.raises(ValueError,match="Boot snapshot differs"):
        boot.prepare(changed_path,campaign_sha256=read.digest(changed_raw),expected_devnum="55",now=now)
