# SPDX-License-Identifier: MIT
"""Reset completion ordering for the Event120 adapter; no standalone opener.

The campaign adapter supplies the exact installation and live connection gates.
Only completion logging differs from the incumbent fixed-loader transport.
"""
import ctypes as C
import fcntl

from fm1_fixed_target_reset import reset, digest


class CompletionFirstReset(reset.ResetSG):
    def request_reset(self):
        try:
            self.prepared.check()
            if self.consumed or self.failed or self.fd is None:
                raise ValueError('Reset attempt already consumed or closed')
            self.consumed = True
            command = C.create_string_buffer(reset.RESET_CDB)
            sense, data = C.create_string_buffer(32), C.create_string_buffer(16)
            h = self.prepared.header_type(interface_id=ord('S'), direction=-3,
                cmd_len=16, sense_max=32, data_len=16, data=C.addressof(data),
                cmd=C.addressof(command), sense=C.addressof(sense), timeout=3000)
            self.log('reset_submit_intent', phase=self.phase,
                cdb=reset.RESET_CDB.hex(), in_len=16, out_len=0,
                retry=False, boot_observed=False)
            self.binding()
            self.ioctl_attempts += 1
            fcntl.ioctl(self.fd, 0x2285, h)
            # Detach is expected after this command. Record the returned SG
            # status before any later device observation can lose that evidence.
            self.log('reset_sg_completion', status=h.status, masked=h.masked,
                msg=h.msg, host=h.host, driver=h.driver, resid=h.resid,
                info=h.info, sense_len=h.sense_len,
                sense_hex=sense.raw[:min(h.sense_len, 32)].hex(),
                response_sha256=digest(data.raw), retry=False, boot_observed=False)
            if (h.status or h.masked or h.msg or h.host or h.driver or h.resid
                    or h.info or h.sense_len or data.raw[:2] != reset.RESET_CDB[:2]):
                raise OSError('Reset reply incomplete or ambiguous')
            self.phase = 'request-completed-boot-unobserved'
            return dict(request_completion=True, core_reset_observed=False,
                        boot_observed=False)
        except BaseException:
            self.failed = True
            self.phase = 'reset-ambiguous-closed'
            raise
        finally:
            self.close()
