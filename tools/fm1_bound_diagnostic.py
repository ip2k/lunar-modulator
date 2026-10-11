"""MIT. Offline/mock transaction-bound diagnostic protocol adapter.

No physical opener, CLI, ROM entry or loader upload exists here. The caller
injects a transport: binding() returns loader/session/identity assertions,
exchange(cdb, payload, in_size) returns exact response bytes, and close() closes
that handle. Assertions are checked, but physical loader/recovery/unit binding
remains unproven. Python objects and caller code are not a security sandbox.
The independent fixed scratch adapter is unchanged.
"""
from dataclasses import dataclass
import binascii
import json
from pathlib import Path
import sys
import time

from fm1_flash_transaction import load_transaction, run_transaction, encoded, digest
from fm1_uboot_read import request, CHUNK, FLASH_SIZE, LOADER_SHA

sys.path.insert(0, str(Path(__file__).resolve().parent / 'jieli'))
import raw_flash_profile as raw  # noqa: E402

SCOPE = 'FM-1_092 bound diagnostic application'
_VALIDATED = object()


def _identity(identity, baseline):
    if (identity.get('simulated') is not False or identity.get('firmware') != 'FM-1_092'
            or identity.get('baseline_sha256') != digest(baseline)
            or any(not isinstance(identity.get(key), str) or not identity[key].strip()
                   for key in ('unit_id', 'usb_port', 'usb_topology'))):
        raise ValueError('Diagnostic identity requires explicit unit/topology/content binding')


@dataclass(frozen=True)
class _Policy:
    directory: Path
    direction: str
    plan_bytes: bytes
    baseline: bytes
    target: bytes
    receipt_bytes: bytes
    sectors: tuple
    _authorization: object

    def bind(self, transport):
        if self._authorization is not _VALIDATED:
            raise ValueError('Policy must come from actual-file validation')
        # File checks precede accepting/touching any injected transport.
        self.check_files()
        return BoundDiagnosticSession(self, transport, _VALIDATED)

    def check_files(self):
        plan, journal, baseline, target = load_transaction(self.directory)
        if (encoded(plan) != self.plan_bytes or baseline != self.baseline or target != self.target):
            raise ValueError('Frozen diagnostic transaction artifacts changed')
        return journal

    def receipt(self):
        return json.loads(self.receipt_bytes)


def load_policy(directory, *, direction, manifest_path, identity_path, reference,
                app_path, elf_path, audit_path=None, diagnostic_profile='inert'):
    """Recompute validation from actual files; no transport is accepted here."""
    if direction not in ('install', 'restore'):
        raise ValueError('Explicit install or restore direction required')
    directory = Path(directory).resolve()
    plan, _, baseline, target = load_transaction(directory)
    if plan['scope'] != SCOPE:
        raise ValueError('Only explicit bound diagnostic scope is permitted')
    identity = json.loads(Path(identity_path).read_bytes())
    if identity != plan['identity']:
        raise ValueError('Identity evidence differs from the immutable plan')
    _identity(identity, baseline)
    result = raw.validate_target(
        baseline, (directory / 'backupB.bin').read_bytes(), target,
        json.loads(Path(manifest_path).read_bytes()), identity, reference,
        Path(app_path).read_bytes(), Path(elf_path).read_bytes(), diagnostic_profile,
        json.loads(Path(audit_path).read_bytes()) if audit_path is not None else None)
    if plan['writable_ranges'] != result['writable_ranges']:
        raise ValueError('Plan ranges must exactly equal derived changed sectors')
    result.update(transaction_plan_sha256=digest(encoded(plan)),
                  command_direction=direction, command_scope=SCOPE,
                  protocol_mock_only=True,
                  physical_binding='Injected assertions; physical loader/recovery binding unproven')
    return _Policy(directory, direction, encoded(plan), baseline, target,
                   encoded(result), tuple(result['allowed_sectors']), _VALIDATED)


class BoundDiagnosticSession:
    """Loader-only guarded wire API; errors latch the handle until fresh bind."""
    def __init__(self, policy, transport, authorization=None):
        if authorization is not _VALIDATED or policy._authorization is not _VALIDATED:
            raise ValueError('Use validated_policy.bind(injected_transport)')
        self._policy, self._transport = policy, transport
        self._latched, self._running = False, False
        self._binding = None
        try:
            binding = self._capture_binding()
            if (binding.get('phase') != 'loader' or binding.get('loader_sha256') != LOADER_SHA
                    or not isinstance(binding.get('session_id'), str) or not binding['session_id'].strip()
                    or binding.get('identity') != json.loads(policy.plan_bytes)['identity']):
                raise ValueError('Wrong loader, identity, topology or session binding')
            self._binding = encoded(binding)
        except BaseException:
            self._stop()
            raise

    def _capture_binding(self):
        binding = self._transport.binding()
        if not isinstance(binding, dict):
            raise ValueError('Explicit injected loader-session binding required')
        return json.loads(encoded(binding))

    def _check(self):
        if self._latched:
            raise OSError('Bound diagnostic handle stopped; acquire a fresh loader session')
        try:
            if encoded(self._capture_binding()) != self._binding:
                raise ValueError('Loader/session binding changed')
        except BaseException:
            self._stop()
            raise

    def _stop(self):
        if not self._latched:
            self._latched = True
            try:
                self._transport.close()
            except BaseException:
                pass  # Preserve the first ambiguous failure, never retry.

    def close(self):
        self._stop()

    def identity(self):
        self._check()
        return json.loads(self._policy.plan_bytes)['identity']

    def _mutation_intent(self, operation, address):
        if not self._running:
            raise ValueError('Mutations require the bound durable transaction run')
        journal = self._policy.check_files()
        if (journal.get('state') != 'running' or journal.get('direction') != self._policy.direction
                or journal.get('intent') != dict(operation=operation, address=address)):
            raise ValueError('Mutation differs from durable direction/intent')

    def build_request(self, op, *, address=0, payload=b''):
        """Every direct cmd/execute path must pass this exact wire policy."""
        if type(address) is not int or not isinstance(payload, bytes):
            raise ValueError('Exact integer address and immutable bytes required')
        if op == 0xFB01:
            if address not in self._policy.sectors or payload:
                raise ValueError('Erase only a derived changed sector')
            self._mutation_intent('erase', address)
            return (op.to_bytes(2, 'big') + address.to_bytes(4, 'big')).ljust(16, b'\xff'), b'', 16
        if op == 0xFB04:
            desired = self._policy.target if self._policy.direction == 'install' else self._policy.baseline
            if (address % CHUNK or address // 4096 * 4096 not in self._policy.sectors
                    or len(payload) != CHUNK or payload != desired[address:address + CHUNK]):
                raise ValueError('Program exact direction-bound 256-byte image page only')
            self._mutation_intent('program', address)
            cdb = (op.to_bytes(2, 'big') + address.to_bytes(4, 'big') + CHUNK.to_bytes(2, 'big')
                   + b'\x00' + binascii.crc_hqx(payload, 0).to_bytes(2, 'little')).ljust(16, b'\xff')
            return cdb, payload, 0
        return request(op, 'loader', address=address, payload=payload)

    def execute(self, cdb, payload=b'', in_size=0):
        self._check()
        if not isinstance(cdb, bytes) or len(cdb) != 16:
            raise ValueError('Exact guarded 16-byte loader CDB required')
        op = int.from_bytes(cdb[:2], 'big')
        address = int.from_bytes(cdb[2:6], 'big') if op in (0xFB01, 0xFB04, 0xFD05) else 0
        if (cdb, payload, in_size) != self.build_request(op, address=address, payload=payload):
            raise ValueError('Malformed CDB, CRC, padding or response length')
        try:
            result = self._transport.exchange(cdb, payload, in_size)
            if not isinstance(result, bytes) or len(result) != in_size:
                raise ValueError('Incomplete or unexpected protocol response')
            if in_size == 16 and int.from_bytes(result[:2], 'big') != op:
                raise ValueError('Wrong protocol response echo')
            if op == 0xFC0A and (result[2], int.from_bytes(result[4:8], 'little')) != (3, 0x856014):
                raise ValueError('Wrong flash query/JEDEC')
            if op == 0xFC14 and not CHUNK <= int.from_bytes(result[2:6], 'big') <= 65535:
                raise ValueError('Unsupported loader buffer size')
            self._check()  # A committed command with changed binding is ambiguous.
            return result
        except BaseException:
            self._stop()
            raise

    def cmd(self, op, *, address=0, payload=b''):
        self._check()
        return self.execute(*self.build_request(op, address=address, payload=payload))

    def online(self):
        response = self.cmd(0xFC0A)
        return response[2], int.from_bytes(response[4:8], 'little')

    def read(self, address, size):
        if (type(address) is not int or type(size) is not int or address % CHUNK or size % CHUNK
                or size <= 0 or not 0 <= address <= FLASH_SIZE - size):
            raise ValueError('Aligned bounded loader reads only')
        chunks, last_alive = [], time.monotonic()
        for offset in range(address, address + size, CHUNK):
            if time.monotonic() - last_alive >= 0.5:
                self.online()
                last_alive = time.monotonic()
            chunks.append(self.cmd(0xFD05, address=offset))
        return b''.join(chunks)

    def erase(self, address):
        self.cmd(0xFB01, address=address)

    def program(self, address, data):
        self.cmd(0xFB04, address=address, payload=data)

    def run(self, checkpoint=None):
        """Fixed-directory/fixed-direction run; stop on failure or completion.

        A new bind is required for restore, completed-journal checks and resume.
        Core fresh readback and journal recovery semantics remain unchanged.
        """
        self._check()
        if self._running:
            raise ValueError('A bound transaction is already running')
        try:
            self._policy.check_files()
            self._running = True
            result = run_transaction(self._policy.directory, self, self._policy.direction, checkpoint)
            result.update(protocol_mock_only=True, hardware_validated=False,
                          physical_loader_recovery_binding_proven=False,
                          transaction_plan_sha256=digest(self._policy.plan_bytes),
                          raw_validation_sha256=digest(self._policy.receipt_bytes))
            return result
        finally:
            self._running = False
            self._stop()
