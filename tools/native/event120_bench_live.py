#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""One-use device38 Event120 transaction adapter; no retries, reset or upload."""
import argparse
import ctypes
from dataclasses import dataclass
import importlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
from weakref import WeakSet

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native.event120_bench_policy import load_policy, USB, PLANS
from native.event120_bench_transactions import pinned, MANIFEST_SHA, BASELINE_SHA
from fm1_flash_transaction import digest

KIND = "fm1-device38-event120-transaction"
SOURCES = {
 "native/event120_bench_transactions.py":"a0711605440b5414feda742f55e458a5ea9628da6bfebb98ffa48a58dc63a2c9",
 "native/event120_bench_policy.py":"80617c7bcf008e886274b006dde109dcd0378160c6f0b1db2efb6bd7e6c00258",
 "fm1_fixed_loader_backup.py":"79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb",
 "fm1_uboot_read.py":"28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57",
 "native/expanded_sg.py":"f18e73b658c9d0b06b03b528c6fd4dd4da511a95102ea44252836d885e1a3700",
 "fm1_bound_diagnostic.py":"25e57ffda466c898df88370069cf4d7fce02134e141ba95516347c30953d1a36",
 "fm1_flash_transaction.py":"d0527efbe74314b30a2cd76897c022a1c7857db888ef6e8f8610dbb329956908",
}
_AUTHORIZED = WeakSet()


def sources():
    for name, sha in SOURCES.items():
        if "PLACEHOLDER" in sha:
            raise ValueError("Source pin not finalized")
        pinned(ROOT/name, sha)
    modules = []
    for name in SOURCES:
        mod = importlib.import_module(name[:-3].replace("/", "."))
        if Path(mod.__file__).resolve() != ROOT/name:
            raise ValueError("Ambient implementation module")
        modules.append(mod)
    return modules[2], modules[3], modules[4]


@dataclass(frozen=True, eq=False)
class Prepared:
    config: bytes
    campaign_sha256: str
    policies: tuple
    mapping: bytes
    bridge: object
    header_type: type
    evidence: tuple
    source_sha256: str

    def check(self):
        if self not in _AUTHORIZED:
            raise ValueError("Exact prepared Event120 object required")
        sources()
        pinned(Path(__file__), self.source_sha256)
        for path, sha, limit in self.evidence:
            pinned(path, sha, limit)
        for p in self.policies:
            p.check_files()


def _read_campaign(path):
    path = Path(path).absolute()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as fp:
        if not stat.S_ISREG(os.fstat(fp.fileno()).st_mode):
            raise ValueError("Direct regular campaign required")
        raw = fp.read(65537)
    if len(raw) > 65536:
        raise ValueError("Bounded campaign required")
    return path, raw


def prepare(path, *, now=None):
    """Validate exact campaign/evidence and passively observe SG mapping only."""
    path, raw = _read_campaign(path)
    c = json.loads(raw)
    fields = {"schema","kind","adapter_sha256","observed_at","receipt","plan","direction","variant","output","sg_binding"}
    if (set(c) != fields or type(c["schema"]) is not int or c["schema"] != 1 or c["kind"] != KIND
            or type(c["observed_at"]) not in (int,float) or not math.isfinite(c["observed_at"])):
        raise ValueError("Exact device38 Event120 campaign required")
    age = (time.time() if now is None else now)-c["observed_at"]
    if not 0 <= age <= 120:
        raise ValueError("Fresh passive observation required")
    pinned(Path(__file__), c["adapter_sha256"])
    bridge, reader, sg = sources()
    receipt, plan, output = (Path(c[k]) for k in ("receipt","plan","output"))
    if any(not p.is_absolute() for p in (receipt,plan,output)):
        raise ValueError("Absolute reviewed paths required")
    parent = output.parent
    if (parent != receipt.parent or path.parent != parent or parent.is_symlink()
            or receipt.is_symlink() or os.path.lexists(output) or stat.S_IMODE(parent.stat().st_mode) != 0o700):
        raise ValueError("Private campaign/output beside exact backup required")
    policy = load_policy(plan, receipt=receipt, direction=c["direction"], variant=c["variant"])
    manifest = json.loads(pinned(receipt/"manifest.json", MANIFEST_SHA, 65536))
    if manifest.get("usb_binding") != USB or json.dumps(c["sg_binding"],sort_keys=True) != json.dumps(manifest.get("sg_binding"),sort_keys=True):
        raise ValueError("Fresh exact device38 USB/SG manifest binding required")
    observed = bridge.discover_sg(USB)
    if json.dumps(observed,sort_keys=True) != json.dumps(c["sg_binding"],sort_keys=True):
        raise ValueError("Live passive SG/sysfs mapping differs")
    marker = parent / (".event120-"+c["variant"]+"-"+c["direction"]+".consumed")
    if os.path.lexists(marker):
        raise ValueError("Variant/direction consumed; no automatic retry")
    p = Prepared(raw,digest(raw),(policy,),json.dumps(c["sg_binding"],sort_keys=True,separators=(",",":"),allow_nan=False).encode("ascii"),
       bridge,reader.SGHeader,((path,digest(raw),65536),),c["adapter_sha256"])
    _AUTHORIZED.add(p)
    p.check()
    return p


def run(prepared, *, session_factory=None, now=None):
    """Execute once; tests inject a mock session and never open hardware."""
    prepared.check()
    c, policy = json.loads(prepared.config), prepared.policies[0]
    age = (time.time() if now is None else now)-c["observed_at"]
    if not 0 <= age <= 120:
        raise ValueError("Passive observation expired before run")
    out = Path(c["output"])
    out.mkdir(mode=0o700,exist_ok=False)
    prepared.bridge.sync_dir(out.parent)
    marker = out.parent / (".event120-"+c["variant"]+"-"+c["direction"]+".consumed")
    with prepared.bridge.private_file(marker) as fp:
        fp.write(prepared.campaign_sha256.encode("ascii")); fp.flush(); os.fsync(fp.fileno())
    prepared.bridge.sync_dir(out.parent)
    transport = None
    with prepared.bridge.private_file(out/"commands.jsonl","w") as events:
        def log(event, **fields):
            events.write(json.dumps(dict(time=time.time(),event=event,**fields),sort_keys=True,allow_nan=False)+"\n")
            events.flush(); os.fsync(events.fileno())
        log("native_transaction_prepared",campaign_sha256=prepared.campaign_sha256,
            source_sha256=SOURCES,adapter_sha256=c["adapter_sha256"],
            backup_manifest_sha256=MANIFEST_SHA,sg_binding=c["sg_binding"],
            variant=c["variant"],direction=c["direction"],retry=False)
        try:
            if session_factory is None:
                _,_,sg=sources()
                transport=sg.RehearsalSG(prepared,policy,log)
                session=policy.bind(transport)
            else:
                session=session_factory(prepared,policy,log)
            result=session.run(checkpoint=log)
            expected=BASELINE_SHA if c["direction"]=="restore" else PLANS[c["variant"]][2]
            if result.get("verified_sha256")!=expected:
                raise ValueError("Complete transaction readback differs")
            final=dict(campaign_sha256=prepared.campaign_sha256,direction=c["direction"],
                variant=c["variant"],verified_sha256=expected,sectors_written=result.get("sectors_written"),
                full_flash_readback_verified=True,boot_observed=False,physical_recovery_verified=False,
                kernel_exclusivity=False,hardware_admitted=False,installable=False)
            log("native_transaction_completed",**final)
            with prepared.bridge.private_file(out/"result.json","w") as fp:
                json.dump(final,fp,sort_keys=True);fp.write("\n");fp.flush();os.fsync(fp.fileno())
            prepared.bridge.sync_dir(out)
            return final
        except BaseException as exc:
            log("native_transaction_stopped",error=type(exc).__name__,detail=str(exc),retry=False)
            raise
        finally:
            if transport is not None:
                transport.close()


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign",type=Path,required=True)
    parser.add_argument("--preflight",action="store_true")
    args=parser.parse_args();os.umask(0o077)
    p=prepare(args.campaign)
    print(json.dumps(dict(preflight=True,hardware_operations=0) if args.preflight else run(p)))

