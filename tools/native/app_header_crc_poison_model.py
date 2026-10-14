"""Offline one-bit SFC/JLFS header-poison model; never emits flash I/O."""
from dataclasses import dataclass
from pathlib import Path
import sys

_JIELI = Path(__file__).resolve().parents[1] / "jieli"
if str(_JIELI) not in sys.path:
    sys.path.insert(0, str(_JIELI))

from inspect_fwsc import crc16, sfc_decode  # noqa: E402
from inspect_stock_flash import record  # noqa: E402

APP_HEADER_OFFSET = 0x4000
HEADER_BYTES = 32


@dataclass(frozen=True)
class PoisonPlan:
    """A mathematical candidate, not a physical write authorization."""
    raw_byte_offset: int
    bit_mask: int
    expected_raw_byte: int
    original_header_crc: int
    poisoned_header_crc: int
    hardware_admitted: bool = False
    installable: bool = False


def _decode_and_check(raw_header: bytes) -> bytes:
    if not isinstance(raw_header, bytes) or len(raw_header) != HEADER_BYTES:
        raise ValueError("exact raw 32-byte app-area header required")
    decoded = sfc_decode(raw_header, 0)
    item = record(decoded, 0)
    if item["name"] != "app_area_head":
        raise ValueError("expected stock app-area header")
    return decoded


def simulate_one_bit_clear(raw_header: bytes, bit_index: int) -> bytes:
    """Return an in-memory raw-header variant after one 1-to-0 bit transition."""
    _decode_and_check(raw_header)
    if type(bit_index) is not int or not 0 <= bit_index < 16:
        raise ValueError("CRC bit index must be in [0, 16)")
    byte_index, bit = divmod(bit_index, 8)
    if not raw_header[byte_index] & (1 << bit):
        raise ValueError("selected raw CRC bit is already clear")
    changed = bytearray(raw_header)
    changed[byte_index] &= ~(1 << bit)
    poisoned = bytes(changed)
    decoded = sfc_decode(poisoned, 0)
    # The SFC transform is bytewise XOR. A header CRC bit mutation leaves all
    # CRC-covered bytes unchanged and must make this valid record fail CRC.
    if decoded[2:] != sfc_decode(raw_header, 0)[2:]:
        raise ValueError("CRC-covered header body changed")
    if crc16(decoded[2:]) == int.from_bytes(decoded[:2], "little"):
        raise ValueError("one-bit mutation did not invalidate header CRC")
    return poisoned


def plan_crc_poison(raw_header: bytes) -> PoisonPlan:
    """Select the lowest set bit of the raw stored CRC for a conditional model."""
    decoded = _decode_and_check(raw_header)
    old_crc = int.from_bytes(decoded[:2], "little")
    raw_word = int.from_bytes(raw_header[:2], "little")
    for bit_index in range(16):
        if raw_word & (1 << bit_index):
            poisoned = simulate_one_bit_clear(raw_header, bit_index)
            poisoned_decoded = sfc_decode(poisoned, 0)
            return PoisonPlan(
                raw_byte_offset=APP_HEADER_OFFSET + bit_index // 8,
                bit_mask=1 << (bit_index % 8),
                expected_raw_byte=poisoned[bit_index // 8],
                original_header_crc=old_crc,
                poisoned_header_crc=int.from_bytes(poisoned_decoded[:2], "little"),
            )
    raise ValueError("raw stored header CRC has no set bit available to clear")


def spl_route(raw_header: bytes, rescue_record_valid: bool,
              rescue_loader_valid: bool) -> str:
    """Model only the verified ordinary-header vs conditional rescue branch."""
    try:
        _decode_and_check(raw_header)
    except (ValueError, UnicodeDecodeError):
        header_valid = False
    else:
        header_valid = True
    if header_valid:
        return "ordinary_xip_selected"
    if rescue_record_valid and rescue_loader_valid:
        return "rescue_scan_entry"
    return "no_verified_entry"


def payload_mutation_permitted(*, poison_readback_invalid: bool,
                               rescue_record_valid: bool,
                               rescue_loader_valid: bool) -> bool:
    """Model the required gate; physical NOR ordering/atomicity is unproven."""
    return (poison_readback_invalid is True
            and rescue_record_valid is True
            and rescue_loader_valid is True)
