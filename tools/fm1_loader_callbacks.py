"""OFFLINE PROPOSAL: fixed loader callback metadata read; never device-executed.

No CLI or device-opening entry point. Separate review is required before use.
This permits no callback execution, ROM/code read, custom payload or flash write.
Pointer values are observations, not proof of their memory region. MIT licence.
"""
from fm1_uboot_read import Reader

CALLBACK_ADDRESS = 0x01C09724
CALLBACK_BYTES = 8


def callback_request(op, phase, *, address, payload=b''):
    if (op != 0xFD07 or phase != 'loader' or
            address != CALLBACK_ADDRESS or payload):
        raise ValueError('Only the fixed two loader callback slots are permitted')
    cdb = (b'\xfd\x07' + CALLBACK_ADDRESS.to_bytes(4, 'big') +
           CALLBACK_BYTES.to_bytes(2, 'big')).ljust(16, b'\xff')
    return cdb, b'', CALLBACK_BYTES


class LoaderCallbackReader(Reader):
    def __init__(self, device, log):
        super().__init__(device, log)
        self._callbacks_ready = False
        self._callbacks_used = False

    def load(self, loader):
        self._callbacks_ready = False
        super().load(loader)
        self._callbacks_ready = True

    def build_request(self, op, address, payload):
        if op != 0xFD07:
            return super().build_request(op, address, payload)
        if not self._callbacks_ready or self._callbacks_used:
            raise ValueError('Callback read requires a verified loader and one attempt')
        result = callback_request(op, self.phase, address=address, payload=payload)
        self._callbacks_used = True  # Consume before transport; never automatically retry.
        return result

    def callbacks(self):
        data = self.cmd(0xFD07, address=CALLBACK_ADDRESS)
        if len(data) != CALLBACK_BYTES:
            raise ValueError('Callback metadata must contain exactly two 32-bit words')
        # Preserve every value. Do not infer a ROM range or strip address bits.
        result = {'send': int.from_bytes(data[:4], 'little'),
                  'receive': int.from_bytes(data[4:], 'little')}
        self.log('loader_callback_slots_observed', address=CALLBACK_ADDRESS,
                 bytes=CALLBACK_BYTES, words_little_endian=result)
        return result
