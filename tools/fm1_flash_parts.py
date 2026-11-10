"""The SPI NOR flash parts known to be fitted to M-VAVE FM-1s, by JEDEC ID.

One allow-list for every Python check that asks "is this an FM-1 flash?".
The ID is the three bytes of the RDID command (9Fh), manufacturer first, as
JieLi's loader reports it (FC0A) and as FM-1-transporter prints it.

- `0x856014`, Puya P25Q80H: the owner's unit [verified: FC0A on 2026-10-26,
  notes/2026-10-26-fm1-stock-v15-recovery.md] and other owners' units
  [reported: FM-1-transporter, fm1-nes, SLOOP]. Timings [reported: Puya
  P25Q80H datasheet V1.7, via notes/2026-11-08-failopen-hardening.md §4].
- `0xB36014`, UCUN UC25HQ80: FM-1s sold from about autumn 2026 [reported:
  SLOOP v2.8.5 release notes quoting The Firmware Hub; fm1-gm PR #76].
  Timings and commands [reported: UCUN UC25HQ80 datasheet V1.2, 2022-01-04,
  Table-7, Table-8.0, Table-17/18]. No UC25HQ80 unit has been on this
  project's bench.

Comparison, sources and the inventory of every site that uses this list:
notes/2026-11-10-flash-uc25hq80.md. MIT licence, like this repository.

Owner-unit tools that pin the exact `info` line (tools/fm1-transporter/
fm1t_m5.py and fm1t_m6.py) deliberately do not use this list: there a different ID means
"not the owner's unit", which is a stop, not a new part.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class FlashPart:
    jedec: int
    vendor: str
    part: str
    size: int
    # Largest page/sector/32 KB/64 KB erase time (tPE, tSE, tBE1, tBE2), ms.
    # Chip erase is left out on purpose: firmware never issues one.
    erase_max_ms: int
    program_max_ms: int        # tPP, one 256-byte page
    source: str

    @property
    def name(self):
        return f'{self.vendor} {self.part}'

    def describe(self):
        return f'{self.name} (JEDEC {self.jedec:06X}, {self.size // 1024} KiB)'


FM1_FLASH_PARTS = {
    0x856014: FlashPart(0x856014, 'Puya', 'P25Q80H', 1 << 20, erase_max_ms=20,
                        program_max_ms=3,
                        source='Puya P25Q80H datasheet V1.7 [reported]'),
    0xB36014: FlashPart(0xB36014, 'UCUN', 'UC25HQ80', 1 << 20, erase_max_ms=10,
                        program_max_ms=3,
                        source='UCUN UC25HQ80 datasheet V1.2, 2022-01-04 [reported]'),
}
FM1_FLASH_JEDEC_IDS = frozenset(FM1_FLASH_PARTS)

# The part whose erase/program path has run on this project's bench, through
# JieLi's USB loader and FM-1-transporter (owner's unit, 2026-10-07/-26).
FM1_FLASH_WRITE_TESTED = frozenset({0x856014})

# Worst case over every part: a bound that must cover any FM-1 uses this.
FM1_FLASH_ERASE_MAX_MS = max(p.erase_max_ms for p in FM1_FLASH_PARTS.values())
FM1_FLASH_PROGRAM_MAX_MS = max(p.program_max_ms for p in FM1_FLASH_PARTS.values())


class UnknownFlash(ValueError):
    """The JEDEC ID is not a flash part known to be fitted to an FM-1."""


def fm1_flash_part(jedec):
    """Return the FlashPart for a JEDEC ID, or raise UnknownFlash."""
    part = FM1_FLASH_PARTS.get(jedec)
    if part is None:
        known = ', '.join(p.describe() for p in FM1_FLASH_PARTS.values())
        raise UnknownFlash(f'Flash JEDEC {jedec:06X} is not a known FM-1 flash part '
                           f'(known: {known}); stopping')
    return part


def require_write_tested(jedec):
    """Refuse a flash write on a part whose write path has not run here."""
    part = fm1_flash_part(jedec)
    if jedec not in FM1_FLASH_WRITE_TESTED:
        raise UnknownFlash(f'{part.describe()}: erase/program through this tool has never '
                           'run on that part; this tool writes only on the Puya P25Q80H '
                           '(JEDEC 856014). Reads and backups are fine; see '
                           'notes/2026-11-10-flash-uc25hq80.md')
    return part
