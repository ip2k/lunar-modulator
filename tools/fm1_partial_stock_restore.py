"""MIT. Separate partial-NOR to exact-stock kernel; production admission closed.

No SG opener, loader upload, reset or retry. Fresh matching dumps are preimages,
not acquisition authority. A genuine reviewed partial-backup/capture lineage
must be implemented before prepare_campaign can grant transport authority.
"""
import binascii
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
from weakref import WeakSet

STOCK_SHA = '96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4'
LOADER_SHA = 'fe6d1bd36c8ffe4674e4a05ee748fe87480b5867fac58230b14ff089d411012c'
TX_SHA = 'd0527efbe74314b30a2cd76897c022a1c7857db888ef6e8f8610dbb329956908'
HEADER_SHA = '28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57'
ACQUISITION_SOURCE_SHA = None
PURPOSE = 'stock_restore'
SCOPE = 'FM-1_092 distinct partial-NOR preimage to exact stock restoration'
FLASH_BYTES, SECTOR_BYTES, PAGE_BYTES = 1048576, 4096, 256
_AUTHORIZED = WeakSet()
_CONSUMED = WeakSet()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_file(path, limit=2 * FLASH_BYTES):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Absolute evidence path required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('Direct regular evidence required')
        fp = os.fdopen(fd, 'rb'); fd = None
        with fp:
            data = fp.read(limit + 1)
        if len(data) > limit:
            raise ValueError('Evidence exceeds bound')
        return data
    finally:
        if fd is not None:
            os.close(fd)


def geometry(partial_a, partial_b, stock, allowed_sectors):
    """Pure byte constraint; caller must authenticate original consumed authority."""
    if (not all(isinstance(x, bytes) and len(x) == FLASH_BYTES
                for x in (partial_a, partial_b, stock)) or partial_a != partial_b):
        raise ValueError('Two identical complete fresh partial dumps required')
    if digest(stock) != STOCK_SHA:
        raise ValueError('Genuine exact full stock required')
    if (not isinstance(allowed_sectors, tuple) or not allowed_sectors
            or any(type(a) is not int or a % SECTOR_BYTES or
                   not 0x4000 <= a <= 0xAC000 for a in allowed_sectors)
            or tuple(sorted(set(allowed_sectors))) != allowed_sectors):
        raise ValueError('Sorted authenticated application sector whitelist required')
    if partial_a[:0x4000]!=stock[:0x4000] or partial_a[0xACF40:]!=stock[0xACF40:]:
        raise ValueError('Exact stock SPL/OTA/cfg/tail bytes required')
    dirty = tuple(a for a in range(0, FLASH_BYTES, SECTOR_BYTES)
                  if partial_a[a:a+SECTOR_BYTES] != stock[a:a+SECTOR_BYTES])
    if not set(dirty) <= set(allowed_sectors):
        raise ValueError('Partial corruption extends outside original mutation authority')
    # Comparing all other bytes protects SPL, OTA/cfg/tail without parsing a torn directory.
    for a in range(0, FLASH_BYTES, SECTOR_BYTES):
        if a not in allowed_sectors and partial_a[a:a+SECTOR_BYTES] != stock[a:a+SECTOR_BYTES]:
            raise ValueError('Protected full-stock bytes changed')
    return dict(purpose=PURPOSE, internal_action='install', preimage_sha256=digest(partial_a),
                desired_sha256=STOCK_SHA, original_allowed_sectors=list(allowed_sectors),
                dirty_sectors=list(dirty), sector_order=[a for a in dirty if a != 0x4000]
                + ([0x4000] if 0x4000 in dirty else []), protected_stock_bytes_verified=True,
                acquisition_verified=False, hardware_validated=False)


def transaction_module():
    import builtins
    import types
    path = Path(__file__).absolute().with_name('fm1_flash_transaction.py')
    source = read_file(path)
    if digest(source) != TX_SHA:
        raise ValueError('Pinned transaction implementation changed')
    if digest(read_file(path.with_name('fm1_uboot_read.py'))) != HEADER_SHA:
        raise ValueError('Pinned transaction geometry source changed')
    module = types.ModuleType('_partial_stock_transaction'); module.__file__ = str(path)
    def exact_import(name,globals=None,locals=None,fromlist=(),level=0):
        if name=='fm1_uboot_read':
            if fromlist!=('FLASH_SIZE','CHUNK') or level!=0:
                raise ValueError('Only reviewed transaction geometry import permitted')
            return types.SimpleNamespace(FLASH_SIZE=FLASH_BYTES,CHUNK=PAGE_BYTES)
        return builtins.__import__(name,globals,locals,fromlist,level)
    private_builtins=dict(vars(builtins));private_builtins['__import__']=exact_import
    module.__dict__['__builtins__']=private_builtins
    exec(compile(source, str(path), 'exec'), module.__dict__)
    return module


def prepare_transaction(directory, partial_a, partial_b, stock, identity, allowed_sectors):
    """Offline files only; this never registers Prepared or authorizes a transport."""
    receipt = geometry(partial_a, partial_b, stock, allowed_sectors)
    if not receipt['dirty_sectors']:
        raise ValueError('Already stock; no partial mutation transaction needed')
    tx = transaction_module()
    return tx.create_transaction(directory, partial_a, partial_b, stock, identity,
        [[a,a+SECTOR_BYTES] for a in receipt['dirty_sectors']], SCOPE,
        commit_sector=0x4000 if 0x4000 in receipt['dirty_sectors'] else None)


def prepare_campaign(path):
    # Deliberately before path interpretation/import/evidence IO.
    if ACQUISITION_SOURCE_SHA is None:
        raise ValueError('Genuine fresh-partial acquisition admission is closed')
    raise ValueError('Reviewed genuine acquisition composition is not implemented')


@dataclass(frozen=True, eq=False)
class Prepared:
    directory: Path
    receipt: Path
    marker: Path
    campaign_sha256: str
    plan_bytes: bytes
    preimage: bytes
    stock: bytes
    binding: bytes
    evidence: tuple
    absent: tuple

    def check(self):
        if self not in _AUTHORIZED:
            raise ValueError('Exact actual-file partial restore instance required')
        if self in _CONSUMED:
            if read_file(self.marker,64) != self.campaign_sha256.encode('ascii'):
                raise ValueError('Consumed partial restore marker changed')
        elif os.path.lexists(self.receipt) or os.path.lexists(self.marker):
            raise ValueError('Partial restore receipt/session already used')
        if any(os.path.lexists(p) for p in self.absent):
            raise ValueError('Required absent lineage artifact appeared')
        for path,data,limit in self.evidence:
            if read_file(path,limit) != data:
                raise ValueError('Frozen partial restore evidence changed')
        # Prefreeze generic loader inputs before its ordinary Path readers.
        expected = {'plan.json':self.plan_bytes,'backupA.bin':self.preimage,
                    'backupB.bin':self.preimage,'target.bin':self.stock}
        for name,data in expected.items():
            if read_file(self.directory/name) != data:
                raise ValueError('Frozen fresh partial transaction changed')
        read_file(self.directory/'journal.json',65536)
        tx=transaction_module();plan,journal,a,b=tx.load_transaction(self.directory)
        if tx.encoded(plan)!=self.plan_bytes or a!=self.preimage or b!=self.stock:
            raise ValueError('Partial transaction differs')
        if plan['scope'] != SCOPE or plan['identity']['simulated'] is not False:
            raise ValueError('Distinct physical-purpose transaction required')
        return journal


def sync_dir(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:os.fsync(fd)
    finally:os.close(fd)


def exclusive(path, data):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    try:
        fp=os.fdopen(fd,'wb');fd=None
        with fp:fp.write(data);fp.flush();os.fsync(fp.fileno())
    finally:
        if fd is not None:os.close(fd)
    sync_dir(Path(path).parent)


class Session:
    """Injected fixed-loader wire only; no implementation opens physical transport."""
    def __init__(self,prepared,transport,log):
        self.prepared,self.transport,self.log=prepared,transport,log
        self.failed=False;self.close_error=None;self.closed=False;self.index=0
        self.uncertain=set()
        try:self.check_binding()
        except BaseException:self.stop();raise

    def close(self):
        if self.close_error is not None:raise self.close_error
        if not self.closed:
            self.closed=True
            try:self.transport.close()
            except BaseException as exc:self.failed=True;self.close_error=exc;raise

    def stop(self):
        self.failed=True
        self.close()

    def check_binding(self):
        if self.failed or self.closed:raise ValueError('Failed or closed partial restore')
        self.prepared.check()
        actual=self.transport.binding()
        if json.dumps(actual,sort_keys=True,separators=(',',':')).encode()!=self.prepared.binding:
            raise ValueError('Fresh partial fixed-loader binding changed')
        if actual.get('phase')!='loader' or actual.get('loader_sha256')!=LOADER_SHA:
            raise ValueError('Exact reviewed fixed loader required')

    def validate_wire(self,cdb,payload,in_size):
        if not isinstance(cdb,bytes) or len(cdb)!=16 or not isinstance(payload,bytes) or type(in_size)is not int:
            raise ValueError('Exact immutable wire request required')
        op=int.from_bytes(cdb[:2],'big');address=int.from_bytes(cdb[2:6],'big')
        if op==0xFC0A:
            expected=(bytes.fromhex('fc0a'+'ff'*14),b'',16)
        elif op==0xFD05:
            if address%256 or not 0<=address<=FLASH_BYTES-256:raise ValueError('Aligned bounded page only')
            expected=((b'\xfd\x05'+address.to_bytes(4,'big')+b'\x01\x00').ljust(16,b'\xff'),b'',256)
        elif op in (0xFB01,0xFB04):
            operation='erase' if op==0xFB01 else 'program'
            journal=self.prepared.check();sectors={a for a,_ in json.loads(self.prepared.plan_bytes)['writable_ranges']}
            if journal.get('state')!='running' or journal.get('direction')!='install' or journal.get('intent')!={'operation':operation,'address':address}:
                raise ValueError('Exact durable mutation intent required at request boundary')
            if address//4096*4096 not in sectors:raise ValueError('Dirty authenticated sectors only')
            if op==0xFB01:
                if address%4096:raise ValueError('Whole sector erase only')
                expected=((b'\xfb\x01'+address.to_bytes(4,'big')).ljust(16,b'\xff'),b'',16)
            else:
                page=self.prepared.stock[address:address+256]
                if address%256 or len(page)!=256:raise ValueError('Whole stock page only')
                prefix=b'\xfb\x04'+address.to_bytes(4,'big')+b'\x01\x00\x00'+binascii.crc_hqx(page,0).to_bytes(2,'little')
                expected=(prefix.ljust(16,b'\xff'),page,0)
        else:raise ValueError('No upload/reset/eFuse or other vendor request permitted')
        if (cdb,payload,in_size)!=expected:raise ValueError('Exact partial restore wire shape differs')

    def exchange(self,cdb,payload=b'',in_size=0):
        try:
            self.check_binding();self.validate_wire(cdb,payload,in_size)
            if self.index>=65536:raise ValueError('Bounded partial command inventory exhausted')
            self.log('partial_request_intent',index=self.index,cdb=cdb.hex(),out_len=len(payload),
                     in_len=in_size,payload_sha256=digest(payload) if payload else None,retry=False)
            self.check_binding();self.validate_wire(cdb,payload,in_size)  # post-intent exact journal check
            self.index+=1
            result=self.transport.exchange(cdb,payload,in_size)
            if not isinstance(result,bytes) or len(result)!=in_size:
                raise ValueError('Exact complete response required')
            self.log('partial_response',index=self.index-1,response_sha256=digest(result),retry=False)
            self.check_binding()
            return result
        except BaseException:self.stop();raise

    def identity(self):
        self.check_binding()
        return json.loads(self.prepared.plan_bytes)['identity']

    def online(self):return self.status()

    def status(self):
        response=self.exchange(bytes.fromhex('fc0a'+'ff'*14),in_size=16)
        if response[:2]!=b'\xfc\x0a' or response[2]!=3 or int.from_bytes(response[4:8],'little')!=0x856014:
            self.stop();raise ValueError('Online fixed NOR geometry differs')
        return 3,0x856014

    def read(self,address,size):
        if type(address)is not int or type(size)is not int or address%256 or size%256 or size<=0 or not 0<=address<=FLASH_BYTES-size:
            raise ValueError('Aligned bounded full pages required')
        data=[]
        for a in range(address,address+size,256):
            cdb=(b'\xfd\x05'+a.to_bytes(4,'big')+b'\x01\x00').ljust(16,b'\xff')
            page=self.exchange(cdb,in_size=256);data.append(page)
            # Only actual successful matching readback clears attempted page uncertainty.
            if page==self.prepared.stock[a:a+256]:self.uncertain.discard(a)
        return b''.join(data)

    def mutation(self,operation,address,payload=b''):
        journal=self.prepared.check();plan=json.loads(self.prepared.plan_bytes)
        if journal.get('state')!='running' or journal.get('direction')!='install' or journal.get('intent')!={'operation':operation,'address':address}:
            raise ValueError('Exact durable stock-restore mutation intent required')
        sectors={a for a,_ in plan['writable_ranges']}
        if operation=='erase':
            if address not in sectors or payload:raise ValueError('Dirty authorized whole sector only')
            cdb=(b'\xfb\x01'+address.to_bytes(4,'big')).ljust(16,b'\xff');in_size=16
            self.uncertain.update(range(address,address+4096,256))
        elif operation=='program':
            if address%256 or address//4096*4096 not in sectors or len(payload)!=256 or payload!=self.prepared.stock[address:address+256]:
                raise ValueError('Exact stock page in dirty authorized sector only')
            cdb=(b'\xfb\x04'+address.to_bytes(4,'big')+b'\x01\x00\x00'+binascii.crc_hqx(payload,0).to_bytes(2,'little')).ljust(16,b'\xff');in_size=0
            self.uncertain.add(address)
        else:raise ValueError('No other mutation permitted')
        response=self.exchange(cdb,payload,in_size)
        if in_size and response[:2]!=cdb[:2]:self.stop();raise ValueError('Erase response differs')

    def erase(self,address):return self.mutation('erase',address)
    def program(self,address,payload):return self.mutation('program',address,payload)


def run_campaign(prepared,transport_factory):
    journal=prepared.check()
    if prepared in _CONSUMED:
        raise FileExistsError('Consumed partial restore cannot be reopened')
    if (journal.get('state')!='prepared' or journal.get('direction') is not None
            or journal.get('intent') is not None):
        raise ValueError('New untouched partial preimage transaction required')
    prepared.receipt.mkdir(mode=0o700,exist_ok=False);sync_dir(prepared.receipt.parent)
    exclusive(prepared.marker,prepared.campaign_sha256.encode('ascii'));_CONSUMED.add(prepared)
    path=prepared.receipt/'commands.jsonl'
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    try:fp=os.fdopen(fd,'w');fd=None
    finally:
        if fd is not None:os.close(fd)
    with fp:
        def log(event,**fields):
            fp.write(json.dumps(dict(event=event,**fields),sort_keys=True)+'\n');fp.flush();os.fsync(fp.fileno());sync_dir(prepared.receipt)
        session=None
        try:
            log('partial_stock_restore_prepared',purpose=PURPOSE,internal_action='install',campaign_sha256=prepared.campaign_sha256,
                preimage_sha256=digest(prepared.preimage),desired_sha256=STOCK_SHA,boot_observed=False,physical_recovery_verified=False)
            prepared.check();session=Session(prepared,transport_factory(),log)
            result=transaction_module().run_transaction(prepared.directory,session,'install',checkpoint=log)
            session.close();prepared.check()
            if result['verified_sha256']!=STOCK_SHA or session.uncertain:
                raise ValueError('Final exact stock readback required')
            output=dict(purpose=PURPOSE,internal_action='install',campaign_sha256=prepared.campaign_sha256,
                verified_sha256=STOCK_SHA,full_flash_readback_verified=True,sectors_written=result['sectors_written'],
                boot_observed=False,physical_recovery_verified=False,kernel_exclusivity=False)
            log('partial_stock_restore_completed',**output)
            exclusive(prepared.receipt/'result.json',json.dumps(output,sort_keys=True).encode()+b'\n')
            return output
        except BaseException as exc:
            try:(prepared.receipt/'result.json').unlink(missing_ok=True);sync_dir(prepared.receipt)
            except OSError:pass
            try:log('partial_stock_restore_stopped_ambiguous',error=type(exc).__name__,retry=False,boot_observed=False)
            except OSError:pass
            raise
        finally:
            if session is not None:session.close()
