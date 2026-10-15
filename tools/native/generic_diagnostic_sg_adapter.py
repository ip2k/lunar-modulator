# SPDX-License-Identifier: MIT
"""Injected bridge from the checked D7000 policy to reviewed RehearsalSG.

No device opener or CLI is supplied. Caller explicitly injects a transport factory.
"""
from dataclasses import dataclass
import hashlib, json, os, stat
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE_SHA256={
 "generic_diagnostic_flash.py":"b6588b26df050f9a43b5e4bc1e2c18eb0a57806b0fc6db96368489b44bfc9651",
 "expanded_candidate.py":"566f8cbf2965ccc3e20f703fa074bb174542df99b3cd22e2d54f7779183cbb59",
 "expanded_sg.py":"f18e73b658c9d0b06b03b528c6fd4dd4da511a95102ea44252836d885e1a3700",
 "event120_generic_boot.py":"a060459933f8e34b34df8a0978e76e65e3d92f6bb728cbeb3306f4ffb132d820",
 "fm1_bound_diagnostic.py":"25e57ffda466c898df88370069cf4d7fce02134e141ba95516347c30953d1a36",
 "fm1_flash_transaction.py":"d0527efbe74314b30a2cd76897c022a1c7857db888ef6e8f8610dbb329956908",
}
def _sha(b): return hashlib.sha256(b).hexdigest()
def _canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),allow_nan=False).encode("ascii")
def _check_sources(pm,sm):
 paths={"generic_diagnostic_flash.py":Path(pm.__file__).resolve(),
 "expanded_candidate.py":ROOT/"native/expanded_candidate.py",
 "expanded_sg.py":Path(sm.__file__).resolve(),
 "event120_generic_boot.py":ROOT/"native/event120_generic_boot.py",
 "fm1_bound_diagnostic.py":ROOT/"fm1_bound_diagnostic.py",
 "fm1_flash_transaction.py":ROOT/"fm1_flash_transaction.py"}
 evidence=[]
 for n,p in paths.items():
  raw=p.read_bytes()
  if _sha(raw)!=SOURCE_SHA256[n]: raise ValueError("Reviewed adapter dependency changed: "+n)
  evidence.append((p,raw,max(len(raw),1)))
 own=Path(__file__).resolve()
 raw=own.read_bytes()
 evidence.append((own,raw,max(len(raw),1)))
 return tuple(evidence)

class DurableLog:
 """Exclusive 0600 JSONL log; fsync each row."""
 def __init__(self,path):
  self.path=Path(path).absolute(); parent=self.path.parent; s=parent.stat(follow_symlinks=False)
  if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)&0o077:
   raise ValueError("Log parent must be owner-only directory")
  self.fd=os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
  if not stat.S_ISREG(os.fstat(self.fd).st_mode):
   os.close(self.fd); self.fd=None; raise ValueError("Log must be regular file")
  d=os.open(parent,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
  try: os.fsync(d)
  finally: os.close(d)
 def __call__(self,event,**fields):
  if self.fd is None: raise ValueError("Log closed")
  v=memoryview(_canon({"event":event,**fields})+b"\n")
  while v:
   n=os.write(self.fd,v)
   if n<=0: raise OSError("Short durable log write")
   v=v[n:]
  os.fsync(self.fd)
 def close(self):
  if self.fd is not None:
   fd=self.fd; self.fd=None; os.fsync(fd); os.close(fd)

@dataclass(frozen=True)
class _Direction:
 policy: object
 direction: str
 binding_bytes: bytes
 @property
 def plan_bytes(self): return self.policy.plan_bytes
 @property
 def baseline(self): return self.policy.baseline
 @property
 def target(self): return self.policy.target
 @property
 def sectors(self): return self.policy.sectors
 def check_files(self): return self.policy.check_files()

class _Prepared:
 def __init__(self,policy,direction,bridge,reader,mapping,campaign,evidence=()):
  self.policy=policy; self.policies=(direction,); self.bridge=bridge
  self.header_type=reader.SGHeader; self.mapping=_canon(mapping)
  self.campaign_sha256=campaign; self.extra_evidence=tuple(evidence)
 def check(self):
  self.policy.check_files()
  for p,raw,_limit in self.extra_evidence:
   if Path(p).read_bytes()!=raw: raise ValueError("Fresh read evidence changed: "+Path(p).name)
  return True


class _LoggedTransport:
    # Couple the durable transaction log to the SG session lifetime.
    def __init__(self, inner, log):
        self.inner, self.log, self.closed = inner, log, False
    def binding(self):
        return self.inner.binding()
    def exchange(self, *args, **kwargs):
        return self.inner.exchange(*args, **kwargs)
    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.inner.close()
        finally:
            self.log.close()

def _verified(pm,policy,direction,restore_read):
 if direction=="install":
  receipt=policy.receipt(); path=None
  for p,raw,_lim in policy.evidence:
   if _sha(raw)==receipt.get("live_manifest_sha256"): path=Path(p); break
  if path is None: raise ValueError("Original read manifest missing from policy evidence")
  manifest=json.loads(path.read_bytes())
  read={"manifest_path":str(path),"manifest_sha256":receipt["live_manifest_sha256"],
        "commands_sha256":manifest["commands_sha256"],"campaign_sha256":receipt["live_campaign_sha256"],
        "expected_devnum":manifest["usb_binding"]["devnum"],"current_flash_sha256":receipt["live_baseline_sha256"]}
 else:
  read=restore_read
  if not isinstance(read,dict) or set(read)!={"manifest_path","manifest_sha256","commands_sha256","campaign_sha256","expected_devnum","current_flash_sha256"}:
   raise ValueError("Restore requires exact fresh dual-read evidence")
 v=pm.generic_boot.verify_read_bundle(read["manifest_path"],read["manifest_sha256"],read["commands_sha256"],
    campaign_sha256=read["campaign_sha256"],expected_devnum=read["expected_devnum"],
    expected_flash_sha256=read["current_flash_sha256"])
 m=v["manifest"]
 if direction=="install":
  req=json.loads(policy.binding_bytes)
  observed={"usb_binding":m["usb_binding"],"sg_binding":m["sg_binding"],
   "read_campaign_sha256":read["campaign_sha256"],"read_manifest_sha256":read["manifest_sha256"],
   "read_commands_sha256":read["commands_sha256"],"baseline_sha256":m["current_flash_sha256"],
   "loader_sha256":m["loader_sha256"]}
  for k,value in observed.items():
   if req.get(k)!=value: raise ValueError("Policy/read binding differs: "+k)
 else:
  old=json.loads(policy.binding_bytes)["usb_binding"]; new=m["usb_binding"]
  if any(old.get(k)!=new.get(k) for k in ("path","busnum","vid","pid")):
   raise ValueError("Restore read is from another stable USB port")
  req={"phase":"loader","loader_sha256":m["loader_sha256"],"usb_binding":m["usb_binding"],
   "sg_binding":m["sg_binding"],"read_campaign_sha256":read["campaign_sha256"],
   "read_manifest_sha256":read["manifest_sha256"],"read_commands_sha256":read["commands_sha256"],
   "baseline_sha256":m["current_flash_sha256"],"identity":json.loads(policy.plan_bytes)["identity"]}
 return read,v,req

def bind(policy,*,policy_module,sg_module,transport_factory,log_path,direction="install",restore_read=None):
 """Return the generic policy's guarded DiagnosticSession over injected RehearsalSG."""
 if direction not in ("install","restore") or not callable(transport_factory):
  raise ValueError("Explicit direction and transport factory required")
 source_evidence=_check_sources(policy_module,sg_module)
 if not isinstance(policy,policy_module.Policy) or policy not in policy_module._POLICIES:
  raise ValueError("Factory-created generic diagnostic policy required")
 policy.check_files(require_fresh=(direction=="install"))
 read,v,req=_verified(policy_module,policy,direction,restore_read)
 dp=_Direction(policy,direction,_canon(req))
 prepared=_Prepared(policy,dp,v["bridge"],v["reader"],v["manifest"]["sg_binding"],
                    read["campaign_sha256"],tuple(v.get("evidence",()))+source_evidence)
 prepared.check(); log=DurableLog(log_path); transport=None; logged=None
 try:
  transport=transport_factory(prepared,dp,log)
  logged=_LoggedTransport(transport,log)
  return policy.bind(logged,direction=direction,restore_read=restore_read)
 except BaseException:
  try:
   if logged is not None: logged.close()
   elif transport is not None: transport.close()
  except BaseException: pass
  log.close(); raise
