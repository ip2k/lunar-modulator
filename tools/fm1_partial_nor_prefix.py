"""MIT. Strict caught mutation prefix and paired fixed-loader wire replay.

Derived from the separately reviewed cef2 returned-restore cursor. No device
opener or authority. Attempted erase/program spans remain uncertain until a
matching FD05 page hash; operation_returned only updates theoretical bytes.
"""
from dataclasses import dataclass
import binascii
import hashlib
import json
import math
from weakref import WeakSet

FLASH = 1048576
ORDER = tuple(range(0x5000, 0x22000, 4096)) + (0x4000,)
_PROOFS = WeakSet()

def digest(data): return hashlib.sha256(data).hexdigest()
def canonical(v): return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode('ascii')

def wire(op, address=0, payload=b''):
    if op == 0xFC0A: return bytes.fromhex('fc0a'+'ff'*14), b'', 16
    if op == 0xFD05:
        if type(address) is not int or address%256 or not 0<=address<=FLASH-256: raise ValueError('Aligned page required')
        return (b'\xfd\x05'+address.to_bytes(4,'big')+b'\x01\x00').ljust(16,b'\xff'), b'', 256
    if op == 0xFB01:
        if address not in ORDER: raise ValueError('Original authorized sector required')
        return (b'\xfb\x01'+address.to_bytes(4,'big')).ljust(16,b'\xff'), b'', 16
    if op == 0xFB04:
        if address%256 or address//4096*4096 not in ORDER or type(payload) is not bytes or len(payload)!=256: raise ValueError('Exact page required')
        return (b'\xfb\x04'+address.to_bytes(4,'big')+b'\x01\x00\x00'+binascii.crc_hqx(payload,0).to_bytes(2,'little')).ljust(16,b'\xff'), payload, 0
    raise ValueError('No other wire operation')

@dataclass(frozen=True,eq=False)
class Prefix:
    expected_nor: bytes
    uncertainty: tuple
    journal_intents: bytes
    initial_verified: bool
    final_verified: bool
    sectors_verified: tuple
    requests: tuple
    times: tuple
    error: str

class _End(Exception): pass


class _Cursor:
    def __init__(self, rows, desired, initial, direction):
        self.rows, self.wire, self.baseline = rows, wire, desired
        self.direction = direction
        self.requests = []
        self.position = self.index = 0
        self.current = bytearray(initial)
        self.uncertainty = ()
        self.intent = None
        self.possible_intents = []
        self.initial = self.final = False
        self.verified = []
        self.pending = None

    def boundary(self, next_name=None, fields=None):
        if self.position == len(self.rows):
            # Journal publication precedes its checkpoint event. A stopped
            # logger may leave precisely the next durable intent or a cleared
            # intent at the next sector_verified boundary, never arbitrary state.
            self.possible_intents = [self.intent]
            if next_name == 'durable_intent': self.possible_intents.append(fields)
            if next_name == 'sector_verified': self.possible_intents.append(None)
            raise _End()

    def add_uncertainty(self, start, end):
        spans = sorted((*self.uncertainty, (start, end)))
        merged = []
        for a,b in spans:
            if merged and a <= merged[-1][1]: merged[-1] = (merged[-1][0],max(b,merged[-1][1]))
            else: merged.append((a,b))
        self.uncertainty = tuple(merged)

    def verified_page(self, start):
        end = start + 256
        spans = []
        for a,b in self.uncertainty:
            if b <= start or a >= end: spans.append((a,b))
            else:
                if a < start: spans.append((a,start))
                if b > end: spans.append((end,b))
        self.uncertainty = tuple(spans)

    def event(self, name, **fields):
        self.boundary(name, fields)
        actual = dict(self.rows[self.position]); actual.pop('time')
        if canonical(actual) != canonical(dict(event=name, **fields)):
            raise ValueError('Interrupted restore order/fields differ at ' + str(self.position))
        self.position += 1
        if name == 'durable_intent': self.intent = fields
        elif name == 'operation_returned':
            operation, address = fields['operation'], fields['address']
            if operation == 'erase': self.current[address:address+4096] = b'\xff' * 4096
            else: self.current[address:address+256] = self.baseline[address:address+256]
            # Native handler return does not prove that NOR accepted the write.
            # Retain every attempted byte until actual matching FD05 readback.
            self.pending = None
        elif name == 'sector_verified':
            self.intent = None; self.verified.append(fields['address'])

    def command(self, op, address=0, payload=b'', response=None):
        cdb, payload, size = self.wire(op, address, payload)
        self.event('sg_submit_intent', index=self.index, direction=self.direction, cdb=cdb.hex(),
            out_len=len(payload), in_len=size,
            payload_sha256=digest(payload) if payload else None, retry=False)
        self.requests.append((cdb, payload, size, response))
        self.index += 1
        if op in (0xFB01, 0xFB04):
            self.add_uncertainty(address,address + (4096 if op == 0xFB01 else 256))
            self.pending = (op, address)
        self.boundary()
        e = dict(self.rows[self.position]); e.pop('time')
        keys = {'event','index','direction','status','masked','msg','host','driver','resid',
            'info','sense_len','sense_hex','retry','response_sha256'}
        if (set(e) != keys or e['event'] != 'sg_completion' or type(e['index']) is not int or
                e['index'] != self.index-1 or e['direction'] != self.direction or e['retry'] is not False or
                any(type(e[k]) is not int for k in ('status','masked','msg','host','driver','resid','info','sense_len')) or
                any(not 0 <= e[k] <= 255 for k in ('status','masked','msg')) or
                any(not 0 <= e[k] <= 65535 for k in ('host','driver')) or
                not 0 <= e['info'] <= 0xffffffff or not 0 <= e['sense_len'] <= 255 or
                not isinstance(e['sense_hex'],str) or len(e['sense_hex']) != min(e['sense_len'],32)*2 or
                any(c not in '0123456789abcdef' for c in e['sense_hex'])):
            raise ValueError('Bounded exact SG completion required')
        sha = e['response_sha256']
        if (size and (not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha))
                or not size and sha is not None):
            raise ValueError('Bounded actual response hash required')
        ambiguous = any(e[k] for k in ('status','masked','msg','host','driver','resid','info','sense_len'))
        wrong_read = response is not None and sha != digest(response)
        self.position += 1
        if ambiguous or wrong_read:
            if self.position != len(self.rows): raise ValueError('Command followed an ambiguous completion')
            self.boundary()
        # Only actual matching readback clears uncertain physical write spans.
        # Native completion and operation_returned do not prove NOR success.
        if op == 0xFD05 and response is not None: self.verified_page(address)

    def read(self, address, size):
        for page in range(address,address+size,256):
            if (self.position < len(self.rows) and
                    self.rows[self.position].get('cdb') == self.wire(0xFC0A)[0].hex()):
                self.command(0xFC0A)
            self.command(0xFD05,page,response=bytes(self.current[page:page+256]))



def verify(raw, initial, desired, *, direction, prepared_fields, completed_fields, stop_event):
    """Actual adapter fields are supplied by the separate pinned file factory.

    Pure callers cannot obtain device authority. Every emitted request/completion
    is replayed; only a caught terminal stop, never a successful transcript, is
    admitted. A malformed/bad final SG completion is terminal and uncertain.
    """
    if type(raw) is not bytes or len(raw)>32*FLASH or direction not in ('install','restore') or any(type(x) is not bytes or len(x)!=FLASH for x in (initial,desired)):
        raise ValueError('Bounded immutable complete images/log required')
    rows=[json.loads(x) for x in raw.decode('utf8').splitlines()]
    if not 2<=len(rows)<=100000 or any(type(x) is not dict for x in rows): raise ValueError('Caught ordered object events required')
    times=tuple(x.get('time') for x in rows)
    if any(type(t) not in (int,float) or not math.isfinite(t) or t<0 for t in times) or list(times)!=sorted(times): raise ValueError('Finite chronology required')
    stop=dict(rows.pop());stop.pop('time');error=stop.get('error')
    wanted=dict(event=stop_event,error=error,retry=False,stock_baseline_restored=False,boot_observed=False)
    if stop_event=='trace_install_stopped_ambiguous':
        detail=stop.get('detail')
        if type(detail) is not str or len(detail)>4096: raise ValueError('Bounded emitted detail required')
        wanted['detail']=detail
    if type(error) is not str or not error or len(error)>128 or canonical(stop)!=canonical(wanted): raise ValueError('Exact caught stop required')
    r=_Cursor(rows,desired,initial,direction)
    try:
        fields=dict(prepared_fields);name=fields.pop('event');r.event(name,**fields)
        r.command(0xFC0A);r.read(0,FLASH);r.initial=True
        for address in ORDER:
            r.read(address,4096);sector=desired[address:address+4096]
            if bytes(r.current[address:address+4096])==sector: continue
            if bytes(r.current[address:address+4096])!=b'\xff'*4096:
                r.event('durable_intent',operation='erase',address=address)
                r.command(0xFC0A);r.command(0xFB01,address)
                r.event('operation_returned',operation='erase',address=address)
            # operation_returned may be missing after successful SG; uncertainty
            # remains regardless of the theoretical state used by later reads.
            r.read(address,4096)
            for page in range(address,address+4096,256):
                payload=desired[page:page+256]
                if payload!=b'\xff'*256:
                    r.event('durable_intent',operation='program',address=page)
                    r.command(0xFC0A);r.command(0xFB04,page,payload)
                    r.event('operation_returned',operation='program',address=page)
            r.read(address,4096);r.event('sector_verified',address=address)
        r.read(0,FLASH);r.final=True
        fields=dict(completed_fields);name=fields.pop('event');r.event(name,**fields)
        r.boundary();raise ValueError('Events after completion')
    except _End:
        if r.position!=len(rows): raise ValueError('Unexpected stopped suffix')
        proof=Prefix(bytes(r.current),r.uncertainty,canonical(r.possible_intents),r.initial,r.final,tuple(r.verified),tuple(r.requests),times,error)
        _PROOFS.add(proof);return proof

def check_dumps(proof,a,b,stock):
    if type(proof) is not Prefix or proof not in _PROOFS: raise ValueError('Exact replay proof required')
    if type(a) is not bytes or len(a)!=FLASH or a!=b or type(stock) is not bytes or len(stock)!=FLASH: raise ValueError('Matching full acquired dumps required')
    if a[:0x4000]!=stock[:0x4000] or a[0x22000:]!=stock[0x22000:]: raise ValueError('Protected bytes differ')
    previous=0
    for start,end in (*proof.uncertainty,(FLASH,FLASH)):
        if a[previous:start]!=proof.expected_nor[previous:start]: raise ValueError('Unexplained NOR change outside attempted spans')
        previous=end
    return dict(partial_sha256=digest(a),uncertain_ranges=[list(x) for x in proof.uncertainty],dual_complete_identical=True)


def verify_wire(records, requests, *, stopped):
    """Paired USBmon records from pinned reset-wire _records, one same address.

    Each request is (CDB,payload,INsize,expected-IN-or-None). Only exact standard
    TUR/INQUIRY plus not-ready REQUEST SENSE may interleave. A stopped last
    intended command may be absent or have a bounded terminal short/error pair;
    no later vendor traffic is admitted. USBmon proves only displayed prefixes.
    """
    rows=records;position=vendor=standards=0;need_sense=False;terminal=False
    def pair(direction,size,out=None):
        nonlocal position,terminal
        if position+1>=len(rows): raise ValueError('Unpaired relevant transfer')
        s,c=rows[position:position+2];position+=2
        if (s.action!='S' or s.direction!=direction or s.status!=-115 or s.length!=size
                or (s.data if out is None else s.data!=out[:32]) or c.action!='C'
                or c.token!=s.token or c.direction!=direction or c.length<0 or c.length>size
                or (direction=='Bo' and c.data)):
            raise ValueError('Exact paired bulk geometry required')
        if c.status or c.length!=size:
            if not stopped or position!=len(rows): raise ValueError('Nonterminal bulk failure')
            terminal=True
        if direction=='Bi' and not terminal and len(c.data)!=min(size,32): raise ValueError('Full displayed response prefix required')
        return c.data
    while position<len(rows):
        cbw=rows[position].data
        if len(cbw)!=31 or cbw[:4]!=b'USBC': raise ValueError('Exact BOT CBW required')
        cdb=cbw[15:];size=int.from_bytes(cbw[8:12],'little');tag=cbw[4:8]
        forms={bytes(16):(0,0),bytes.fromhex('120000002400')+bytes(10):(36,128),bytes.fromhex('030000001200')+bytes(10):(18,128)}
        is_vendor=cdb[:2] in (b'\xfc\x0a',b'\xfd\x05',b'\xfb\x01',b'\xfb\x04')
        if is_vendor:
            if need_sense or vendor>=len(requests): raise ValueError('Unexpected vendor command')
            expected,payload,in_size,response=requests[vendor]
            if cdb!=expected or size!=(len(payload) or in_size) or cbw[12:15]!=bytes((0 if payload else 128,0,16)): raise ValueError('Ordered direction-bound CDB inventory differs')
            pair('Bo',31,cbw)
            vendor+=1
            if terminal: break
            data=pair('Bo',len(payload),payload) if payload else pair('Bi',in_size)
            if terminal: break
            if not payload and in_size==16 and (data[:2]!=expected[:2] or expected[:2]==b'\xfc\x0a' and (data[2]!=3 or int.from_bytes(data[4:8],'little')!=0x856014)):
                raise ValueError('Fixed loader echo/NOR geometry differs')
            if response is not None and not payload and data!=response[:32]: raise ValueError('Captured response prefix differs from actually verified bytes')
            csw=pair('Bi',13)
            if terminal: break
            if csw!=b'USBS'+tag+bytes(5): raise ValueError('Exact successful vendor CSW required')
        else:
            if terminal or cbw[13:15]!=b'\x00\x06' or cdb not in forms or forms[cdb]!=(size,cbw[12]): raise ValueError('Upload/reset/other kernel operation rejected')
            pair('Bo',31,cbw)
            if terminal: raise ValueError('Kernel transfer failure cannot authorize retained loader')
            sense=bytes.fromhex('030000001200')+bytes(10)
            if need_sense and cdb!=sense: raise ValueError('Immediate not-ready sense required')
            data=pair('Bi',size) if size else b''
            if terminal: raise ValueError('Kernel failure not acquisition provenance')
            csw=pair('Bi',13)
            wanted=b'USBS'+tag+bytes(4)
            if cdb==bytes(16):
                if csw not in (wanted+b'\x00',wanted+b'\x01'): raise ValueError('Exact TUR CSW')
                need_sense=csw[-1]==1
            elif cdb==sense:
                if not need_sense or data!=bytes.fromhex('700002000000000a000000003a0000000000') or csw!=wanted+b'\x00': raise ValueError('Exact immediate sense')
                need_sense=False
            elif need_sense or csw!=wanted+b'\x00': raise ValueError('Kernel inquiry order/status')
            standards+=1
    if need_sense: raise ValueError('Unfinished kernel sense pair')
    # The final durable host intent can precede ioctl, therefore zero traffic
    # for that last request is valid only in the explicit caught-stop branch.
    if vendor!=len(requests) and not (stopped and vendor==len(requests)-1): raise ValueError('Host/capture request prefix differs')
    return dict(vendor_commands=vendor,standard_commands=standards,terminal_transfer_ambiguous=terminal,full_payload_wire_verified=False)
