import hashlib,json,os,pathlib,shutil,subprocess,sys,tarfile
P=pathlib.Path; index=int(sys.argv[1]); jobs=P('/jobs'); work=P('/tmp/inputs');shutil.copytree(jobs,work)
inv=json.loads((work/'closed-entry-stage-inventory.json').read_text());old=P(inv['preserved_original_stage']);root=P(inv['root']);stage=P(inv['stage'])
old.mkdir(parents=True,mode=0o700);old.chmod(0o700)
with tarfile.open(work/'preserved-stage-test-fixture.tar') as t:
 for m in t:
  assert m.isfile() and '..' not in P(m.name).parts and not m.name.startswith('/')
  path=old/m.name;path.parent.mkdir(parents=True,exist_ok=True,mode=0o700);path.write_bytes(t.extractfile(m).read());path.chmod(0o600)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(recovery=False,pin=None,archive=None):
 source=work/('stage-recovery-source-files-proposal.py' if recovery else 'stage-closed-files-proposal.py')
 a=archive or work/('closed-recovery-source-proposal.tar' if recovery else 'closed-main-proposal.tar')
 i=work/('closed-recovery-source-inventory.json' if recovery else 'closed-entry-stage-inventory.json')
 return subprocess.run(['/usr/bin/python3','-B','-E','-s','-S',str(source),'--archive',str(a),'--inventory',str(i),'--expected-self-sha256',pin or digest(source)],capture_output=True,text=True)
def ok(r):assert r.returncode==0,r.stdout+r.stderr
def refuse(r,reason):assert r.returncode!=0 and reason in r.stderr,r.stdout+r.stderr
sample=old/next(iter(inv['preserved_stage_required_files']))
if index==0:
 ok(run());ok(run(True))
 for name,meta in inv['files'].items():
  prefix,relative=name.split('/',1);path=(root if prefix=='entry' else stage)/relative
  assert digest(path)==meta['sha256'] and path.stat().st_mode&0o777==0o600
elif index==1:
 p=work/'closed-main-proposal.tar';p.write_bytes(p.read_bytes()+b'bad');refuse(run(),'exact sealed archive and inventory required')
elif index==2:
 p=work/'closed-entry-stage-inventory.json';p.write_bytes(p.read_bytes()+b' ');refuse(run(),'exact sealed archive and inventory required')
elif index==3:refuse(run(pin='0'*64),'reviewed staging helper SHA differs')
elif index in (4,5):
 (root if index==4 else stage).mkdir(mode=0o700);refuse(run(),'both fresh destinations must be absent')
elif index in (6,7):
 (root if index==6 else stage).symlink_to(old,target_is_directory=True);refuse(run(),'both fresh destinations must be absent')
elif index==8:sample.write_bytes(sample.read_bytes()+b'bad');refuse(run(),'existing sealed campaign asset differs')
elif index==9:
 target=work/'symlink-target';target.write_bytes(sample.read_bytes());sample.unlink();sample.symlink_to(target);refuse(run(),'Too many levels of symbolic links')
elif index==10:old.chmod(0o755);refuse(run(),'root-owned private0700 directory required')
elif index==11:sample.chmod(0o644);refuse(run(),'bounded direct regular private input required')
elif index==12:
 p=work/'archive-link';p.symlink_to(work/'closed-main-proposal.tar');refuse(run(archive=p),'Too many levels of symbolic links')
elif index==13:refuse(run(archive=work),'bounded direct regular private input required')
elif index==14:
 ok(run());p=stage/'tools/fm1_fixed_loader_backup.py';p.write_bytes(p.read_bytes()+b'bad');refuse(run(True),'main STAGE exact tool source differs')
elif index==15:
 ok(run());r=json.loads((work/'closed-recovery-source-inventory.json').read_text());P(r['roots']['acquire']).mkdir(mode=0o700);refuse(run(True),'absent')
else:raise ValueError('exact16 cases')
# Protected original fixture must remain exact except intentional negative mutations.
if index not in (8,9,10,11):
 for name,meta in inv['preserved_stage_required_files'].items():assert digest(old/name)==meta['sha256']
result={'case':index,'passed':True,'hardware_available':False,'main_staged_in_container':index in (0,14,15),'recovery_staged_in_container':index==0}
P('/evidence/case-%02d.json'%index).write_text(json.dumps(result)+'\n');print(json.dumps(result))
