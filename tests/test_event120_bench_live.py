"""Offline injected Event120 lifecycle/refusal tests; never open SG or USB."""
import json, os, shutil, time
from pathlib import Path
import pytest
from tools.native import event120_bench_live as live
from tools.native.event120_bench_policy import PLANS
from tools.native.event120_bench_transactions import BASELINE_SHA

ROOT=Path(os.environ.get("EVENT120_TEST_PRIVATE_ROOT", "/home/claude/.local/share/codex-private"))
PREPARED=ROOT/"device38-event120-transactions-20261014/prepared-002"
BACKUP=ROOT/"device38-backup-20261014/fresh-backup-001"

class FakeBridge:
 def __init__(self,binding): self.binding=binding
 def discover_sg(self,usb):
  assert usb==live.USB
  return self.binding
 def sync_dir(self,path):
  fd=os.open(path,os.O_RDONLY)
  try: os.fsync(fd)
  finally: os.close(fd)
 def private_file(self,path,mode="wb"): return open(path,mode)
class FakeReader:
 class SGHeader: pass
class NoSG:
 @staticmethod
 def RehearsalSG(*a,**k): raise AssertionError("real SG transport forbidden in mocks")
class FakeSession:
 def __init__(self,policy,log,fail=False): self.policy,self.log,self.fail=policy,log,fail
 def run(self,checkpoint=None):
  if self.fail: raise OSError("injected mock failure")
  address=self.policy.sectors[0]
  self.log("durable_intent",operation="erase",address=address)
  self.log("operation_returned",operation="erase",address=address)
  self.log("sector_verified",address=address)
  target=self.policy.baseline if self.policy.direction=="restore" else self.policy.target
  import hashlib
  return {"verified_sha256":hashlib.sha256(target).hexdigest(),"sectors_written":len(self.policy.sectors)}

@pytest.fixture
def actual_inputs(tmp_path,monkeypatch):
 if not PREPARED.is_dir() or not BACKUP.is_dir(): pytest.skip("Private device38 plans and backup unavailable")
 stage=tmp_path/"stage";stage.mkdir(mode=0o700)
 receipt=stage/"fresh-backup-001";shutil.copytree(BACKUP,receipt)
 manifest=json.loads((receipt/"manifest.json").read_bytes())
 monkeypatch.setattr(live,"sources",lambda:(FakeBridge(manifest["sg_binding"]),FakeReader,NoSG))
 return stage,receipt,manifest

def make_campaign(stage,receipt,variant="native",direction="install",observed=None,plan=None):
 plan=Path(plan) if plan else PREPARED/("event120-candidate" if variant=="native" else "stock-rollback")
 output=stage/("out-"+variant+"-"+direction)
 import hashlib
 row=dict(schema=1,kind=live.KIND,adapter_sha256=hashlib.sha256(Path(live.__file__).read_bytes()).hexdigest(),
  observed_at=time.time() if observed is None else observed,receipt=str(receipt),plan=str(plan),
  direction=direction,variant=variant,output=str(output),
  sg_binding=json.loads((receipt/"manifest.json").read_bytes())["sg_binding"])
 path=stage/("campaign-"+variant+"-"+direction+".json")
 path.write_text(json.dumps(row,sort_keys=True)+"\n")
 return path

@pytest.mark.parametrize("direction",["install","restore"])
def test_stock_plans_admitted_offline(actual_inputs,direction):
 stage,receipt,_=actual_inputs
 p=live.prepare(make_campaign(stage,receipt,"stock",direction))
 assert len(p.policies[0].sectors)==213
 assert p.policies[0].receipt()["hardware_admitted"] is False

def test_prepared_mapping_matches_rehearsal_canonical_binding(actual_inputs):
 stage,receipt,_=actual_inputs;prepared=live.prepare(make_campaign(stage,receipt,"native","install"))
 from tools.native.expanded_sg import canonical
 expected=json.loads((receipt/"manifest.json").read_bytes())["sg_binding"]
 assert prepared.mapping==canonical(expected)

def test_native_candidate_receipt_chain_is_canonically_bound(actual_inputs):
 stage,receipt,_=actual_inputs
 p=live.prepare(make_campaign(stage,receipt,"native","install"))
 assert len(p.policies[0].sectors)==208
 assert p.policies[0].receipt()["hardware_admitted"] is False

def test_mock_success_logs_compatible_events_and_is_one_use(actual_inputs):
 stage,receipt,_=actual_inputs;path=make_campaign(stage,receipt,"stock","restore");p=live.prepare(path)
 result=live.run(p,session_factory=lambda prep,policy,log:FakeSession(policy,log))
 assert result["verified_sha256"]==BASELINE_SHA and result["hardware_admitted"] is False
 out=Path(json.loads(path.read_text())["output"])
 rows=[json.loads(x) for x in (out/"commands.jsonl").read_text().splitlines()]
 names=[x["event"] for x in rows]
 assert names[0]=="native_transaction_prepared"
 assert {"durable_intent","operation_returned","sector_verified","native_transaction_completed"}<=set(names)
 assert (stage/".event120-stock-restore.consumed").is_file()
 with pytest.raises((ValueError,FileExistsError)): live.prepare(path)

def test_expired_observation_refuses_before_output_or_marker(actual_inputs):
 stage,receipt,_=actual_inputs;path=make_campaign(stage,receipt,observed=time.time()-121)
 with pytest.raises(ValueError,match="Fresh passive"): live.prepare(path)
 assert not (stage/"out-native-install").exists()
 assert not (stage/".event120-native-install.consumed").exists()

@pytest.mark.parametrize("mutation",["wrong_binding","wrong_plan","wrong_direction"])
def test_mutated_campaign_refuses_before_transport(actual_inputs,mutation):
 stage,receipt,_=actual_inputs;path=make_campaign(stage,receipt,"stock","restore");row=json.loads(path.read_text())
 if mutation=="wrong_binding": row["sg_binding"]["node"]="/dev/sg1"
 elif mutation=="wrong_plan": row["plan"]=str(PREPARED/"event120-candidate")
 else: row["direction"]="reset"
 path.write_text(json.dumps(row))
 with pytest.raises((ValueError,OSError)): live.prepare(path)
 assert not Path(row["output"]).exists()

def test_mock_failure_consumes_marker_and_disables_retry(actual_inputs):
 stage,receipt,_=actual_inputs;path=make_campaign(stage,receipt,"stock","restore");p=live.prepare(path)
 with pytest.raises(OSError,match="injected mock failure"):
  live.run(p,session_factory=lambda prep,policy,log:FakeSession(policy,log,fail=True))
 assert (stage/".event120-stock-restore.consumed").is_file()
 rows=[json.loads(x) for x in (stage/"out-stock-restore/commands.jsonl").read_text().splitlines()]
 assert rows[-1]["event"]=="native_transaction_stopped"
 with pytest.raises((ValueError,FileExistsError)): live.prepare(path)

