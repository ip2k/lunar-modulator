"""MIT. Expanded-image command budget with the existing exact SG wire guards.

The class body is byte-identical to the reviewed fixed-loader transport.
No ROM entry, upload, reset, retry, or standalone opener is added here.
"""
import binascii
import ctypes as C
import fcntl
import json
import os
import stat
import time
from fm1_flash_transaction import digest

# Worst-case 213-sector rebuild: 18416 reads + 7242 mutation/query commands.
# Leave bounded room for half-second loader liveness queries on slow USB.
COMMAND_LIMIT = 32768
LIVE_SECONDS = 2700


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")


class RehearsalSG:
    """Exact policy direction, live FD/sysfs binding and fail-closed SG status."""
    def __init__(self, prepared, policy, log):
        prepared.check()
        if not any(policy is p for p in prepared.policies):
            raise ValueError('Exact prepared direction policy required')
        self.prepared, self.policy, self.log = prepared, policy, log
        self.fd, self.failed, self.attempts = None, False, 0
        self.close_error = None
        self.started = time.monotonic()
        self.usb = json.loads(policy.binding_bytes)['usb_binding']
        self.expected = json.loads(policy.binding_bytes)
        self.session_id = prepared.campaign_sha256 + ':' + policy.direction
        try:
            self.mapping = prepared.bridge.discover_sg(self.usb)
            if canonical(self.mapping) != prepared.mapping:
                raise ValueError('Backup connection replaced')
            self.fd = os.open(self.mapping['node'], os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.binding()
        except BaseException:
            self.failed = True
            self.close()
            raise

    def close(self):
        if self.close_error is not None:
            raise self.close_error
        if self.fd is not None:
            fd, self.fd = self.fd, None
            try:
                os.close(fd)
            except BaseException as exc:
                self.failed = True
                self.close_error = exc
                raise

    def binding(self):
        if self.failed or self.fd is None or not 0 <= time.monotonic() - self.started <= LIVE_SECONDS:
            raise ValueError('Closed, failed or stale rehearsal connection')
        opened = os.fstat(self.fd)
        if (not stat.S_ISCHR(opened.st_mode)
                or canonical((opened.st_dev, opened.st_ino, opened.st_rdev)) != canonical(self.mapping['node_identity'])
                or canonical(self.prepared.bridge.discover_sg(self.usb)) != self.prepared.mapping):
            self.failed = True
            self.close()
            raise ValueError('Bound SG/sysfs/USB connection replaced')
        return dict(self.expected, phase='loader', loader_sha256=self.prepared.bridge.LOADER_SHA,
                    session_id=self.session_id, identity=json.loads(self.policy.plan_bytes)['identity'])

    def validate_wire(self, cdb, payload, in_size):
        if not isinstance(cdb, bytes) or len(cdb) != 16 or not isinstance(payload, bytes) or type(in_size) is not int:
            raise ValueError('Exact immutable wire request required')
        op, address = int.from_bytes(cdb[:2], 'big'), int.from_bytes(cdb[2:6], 'big')
        if op == 0xFC0A:
            expected = bytes.fromhex('fc0a' + 'ff' * 14), b'', 16
        elif op == 0xFD05:
            if address % 256 or not 0 <= address <= 1048576 - 256:
                raise ValueError('Aligned full-flash read only')
            expected = (b'\xfd\x05' + address.to_bytes(4, 'big') + b'\x01\x00').ljust(16, b'\xff'), b'', 256
        elif op in (0xFB01, 0xFB04):
            # Read requests cannot mutate NOR. Before each mutation, recheck
            # every actual-file gate and reviewed implementation source.
            self.prepared.check()
            journal = self.policy.check_files()
            operation = 'erase' if op == 0xFB01 else 'program'
            if (journal.get('state') != 'running' or journal.get('direction') != self.policy.direction
                    or journal.get('intent') != dict(operation=operation, address=address)):
                raise ValueError('Exact durable direction/mutation intent required')
            if op == 0xFB01:
                if address not in self.policy.sectors:
                    raise ValueError('Derived 4 KiB erase sector only')
                expected = (b'\xfb\x01' + address.to_bytes(4, 'big')).ljust(16, b'\xff'), b'', 16
            else:
                desired = self.policy.target if self.policy.direction == 'install' else self.policy.baseline
                if (address % 256 or address // 4096 * 4096 not in self.policy.sectors
                        or len(payload) != 256 or payload != desired[address:address + 256]):
                    raise ValueError('Exact direction-bound page only')
                prefix = (b'\xfb\x04' + address.to_bytes(4, 'big') + b'\x01\x00\x00'
                          + binascii.crc_hqx(payload, 0).to_bytes(2, 'little'))
                expected = prefix.ljust(16, b'\xff'), payload, 0
        else:
            raise ValueError('No other command is permitted in a rehearsal')
        if (cdb, payload, in_size) != expected:
            raise ValueError('CDB, CRC, padding, payload or response shape differs')

    def exchange(self, cdb, payload=b'', in_size=0):
        try:
            self.binding()
            self.validate_wire(cdb, payload, in_size)
            if self.attempts >= COMMAND_LIMIT:
                raise ValueError('Rehearsal command limit reached')
            index = self.attempts
            self.attempts += 1  # An attempted command is never retried on this handle.
            command, sense = C.create_string_buffer(cdb), C.create_string_buffer(32)
            data = C.create_string_buffer(payload) if payload else C.create_string_buffer(in_size)
            h = self.prepared.header_type(interface_id=ord('S'), direction=-2 if payload else -3,
                cmd_len=16, sense_max=32, data_len=len(payload) or in_size,
                data=C.addressof(data), cmd=C.addressof(command), sense=C.addressof(sense), timeout=3000)
            self.log('sg_submit_intent', index=index, direction=self.policy.direction, cdb=cdb.hex(),
                     out_len=len(payload), in_len=in_size, payload_sha256=digest(payload) if payload else None,
                     retry=False)
            self.binding()
            self.validate_wire(cdb, payload, in_size)
            fcntl.ioctl(self.fd, 0x2285, h)
            self.log('sg_completion', index=index, direction=self.policy.direction, status=h.status,
                     masked=h.masked, msg=h.msg, host=h.host, driver=h.driver, resid=h.resid, info=h.info,
                     sense_len=h.sense_len, sense_hex=sense.raw[:min(h.sense_len, 32)].hex(),
                     response_sha256=digest(data.raw[:in_size]) if in_size else None, retry=False)
            self.binding()
            if (h.status or h.masked or h.msg or h.host or h.driver or h.resid or h.info or h.sense_len):
                raise OSError('Incomplete or ambiguous SG completion')
            result = data.raw[:in_size]
            if (in_size == 16 and result[:2] != cdb[:2]
                    or cdb[:2] == b'\xfc\x0a' and (result[2], int.from_bytes(result[4:8], 'little')) != (3, 0x856014)):
                raise ValueError('Protocol response differs')
            return result
        except BaseException:
            self.failed = True
            self.close()
            raise

