#!/usr/bin/env python3
"""Offline evidence-oriented pi32v2 analysis; no device or vendor-tool dependency.

This is a partial instruction decoder, not a decompiler. Unknown instructions
retain their bytes. Names borrowed from prior analysis are explicitly inferred.
See docs/13-firmware-decoding.md for address proofs and research provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

try:
    from .fm1_package import inspect_application, MAX_INPUT_SIZE
    from .fm1_dsp import analyze_dsp_tables
    from .fm1_effects import analyze_effects
except ImportError:
    from fm1_package import inspect_application, MAX_INPUT_SIZE
    from fm1_dsp import analyze_dsp_tables
    from fm1_effects import analyze_effects


V15_SHA256 = "306e47065f35d7a7a05ada7f5dd092f6e770952054f33f0a86b75fd10ffe3203"
V009_SHA256 = "73f37ac3db15f5e70ae718dac43ab30055a0e27f659ae1b3eeb4c51a39b1616a"
REFERENCE_REVISION = "95eca8488ac8c3b6f86287b2d3d43678e03e271a"
XIP_BASE = 0x02000120
RAM_BASE = 0x01C00000
RAM_FILE_OFFSET = 0x83F40
RAM_SIZE = 0xA05C
MAX_STRINGS = 4096
MAX_DISASSEMBLY_BYTES = 65536
SPECIAL_REGISTERS = (
    "reti", "rete", "retx", "rets", "sr4", "psr", "cnum", "uspn",
    "sspn", "icfgn", "icfgs", "icfg", "usp", "ssp", "sp", "pc",
)

# Only fingerprints and annotations are distributed, never firmware payloads.
# V15 function spans are freshly bounded by observed prologue/return pairs.
# Their semantic names remain hypotheses corroborated by data/call evidence.
_V15_FUNCTIONS = [
    ("reset_and_crt", 0, 198, "4810d5d59c44e93586a667e41dcef05706379b9aa157b37c9b46e9c45a6a2371", "startup", "verified", None),
    ("fm_operator_kernel_candidate", 0x85064, 544, "92017cba35125f6258bf30bcbe4ae3008babf18afbc0e1c6e4e6cca975e7c9e7", "synthesis", "inferred", 0x85824),
    ("fm_core_render_candidate", 0x85284, 2270, "d382c2d836c686c9cce9dba22142eba5556687991c685f39275fa6b38dad0680", "synthesis", "inferred", 0x85A28),
    ("dx7note_compute_block_candidate", 0x85B62, 2054, "22552cc5b58aa5841667f53df820fcc42e6cfd85568e0df45a77e06fbd11fbdf", "synthesis", "inferred", 0x862FA),
    ("fx_chain_process_candidate", 0x872BE, 656, "2575f84297ba0bfbe772fb8cc46cf632fd1440c0a559ebef449c2d7e47833760", "effects", "inferred", 0x87A26),
    ("envelope_update_candidate", 0x1896, 208, "c49189757d64e629c1a7da7c68729bedd1d46362a502b4d8421dde7d2965c752", "synthesis", "inferred", 0x1888),
]


class DecodeError(ValueError):
    """Invalid input or a requested byte range outside the application."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _signed(value: int, bits: int) -> int:
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def _validate(blob: bytes) -> None:
    if not isinstance(blob, bytes) or not blob or len(blob) > MAX_INPUT_SIZE:
        raise DecodeError(f"application must contain 1 to {MAX_INPUT_SIZE} bytes")


def instruction_size(first_halfword: int) -> int:
    """pi32v2 width, independently checked against 199,931 oracle entries."""
    if not isinstance(first_halfword, int) or not 0 <= first_halfword <= 0xFFFF:
        raise DecodeError("instruction halfword must be an unsigned 16-bit integer")
    return 6 if first_halfword & 0xFF00 == 0xFF00 else 4 if first_halfword >> 13 == 7 else 2


def compact_immediate(encoded: int) -> int:
    """Expand the ISA's replicated-byte/shifted-mantissa 12-bit constant."""
    if type(encoded) is not int or not 0 <= encoded < 4096:
        raise DecodeError("compact immediate must be an unsigned 12-bit integer")
    byte = encoded & 0xFF
    if encoded < 0x400:
        return (byte, byte | byte << 16, byte << 8 | byte << 24, byte * 0x01010101)[encoded >> 8]
    return (0x80 | encoded & 0x7F) << (32 - (encoded >> 7))


def decode_instruction(blob: bytes, file_offset: int, address: int | None = None) -> dict:
    """Decode one instruction at a caller-supplied boundary.

    A recognized opcode does not establish that arbitrary input is executable.
    Relative targets are absent when the caller has no justified runtime map.
    """
    if not isinstance(blob, bytes) or not isinstance(file_offset, int) or file_offset < 0 or file_offset >= len(blob):
        raise DecodeError("instruction offset lies outside application")
    if address is not None and (not isinstance(address, int) or not 0 <= address <= 0xFFFFFFFF):
        raise DecodeError("runtime address must be an unsigned 32-bit integer")
    remaining = len(blob) - file_offset
    word = int.from_bytes(blob[file_offset:file_offset + 2], "little")
    width = instruction_size(word) if remaining >= 2 else 2
    size = min(width, remaining)
    raw = blob[file_offset:file_offset + size]
    result = {"file_offset": file_offset, "address": address, "size": size,
              "bytes": raw.hex(), "mnemonic": "unknown", "text": ".byte " + raw.hex(),
              "supported": False, "expected_size": width}
    if word >> 13 == 6 or (width == 4 and word & 0xFF00 in (0xF000, 0xF100)):
        result["parallel_pair"] = True
    if size != width:
        result["text"] = "truncated instruction: " + raw.hex()
        return result
    extra = int.from_bytes(raw[2:], "little")
    # Group 6 is a group-0 instruction issued in a parallel pair. Preserve the
    # pairing marker; this decoder does not emulate parallel execution effects.
    pair = word >> 13 == 6
    w = word & 0x1FFF if pair else word
    group = w >> 13
    ra, rb = w & 15, w >> 4 & 15
    a, b = w & 7, w >> 4 & 7
    def emit(mnemonic: str, text: str, **fields: object) -> dict:
        result.update(mnemonic=mnemonic, text=text, supported=True, **fields)
        if pair:
            result["parallel_pair"] = True
        return result
    def branch(kind: str, displacement: int, **fields: object) -> dict:
        target = (address + width + displacement) & 0xFFFFFFFF if address is not None else None
        desc = f"0x{target:08x}" if target is not None else f"pc+{width}{displacement:+d}"
        return emit(kind, f"{kind} {desc}", target=target, displacement=displacement, **fields)
    def memory(kind: str, register: str, base: str, displacement: int, access_size: int, update: str | None = None) -> dict:
        store = kind.startswith("s")
        expression = f"[{base}{displacement:+d}]" + (f" ({update})" if update else "")
        return emit(kind, f"{kind} {register}, {expression}", register=register,
                    memory={"base": base, "offset": displacement, "width": access_size,
                            "access": "write" if store else "read", "update": update})

    if word == 0xFF80:
        if extra & 1:
            return branch("gotoss", _signed(extra & ~1, 32))
        return branch("call", _signed(extra, 32))
    if width == 6 and word & 0xFFDF in (0xFF00, 0xFF01, 0xFF02, 0xFF03, 0xFF08, 0xFF09, 0xFF0A, 0xFF0B, 0xFF0C, 0xFF0D):
        form = word & 0xDF
        comparison, signed = {0: ("==", True), 1: ("!=", True), 2: (">=", False), 3: ("<", False),
                              8: (">", False), 9: ("<=", False), 10: (">=", True), 11: ("<", True),
                              12: (">", True), 13: ("<=", True)}[form]
        constant = compact_immediate(extra & 0xFFF) if word & 0x20 else _signed(extra & 0xFFF, 12) if signed else extra & 0xFFF
        register = f"r{extra >> 12 & 15}"
        instruction = branch("branch_if", _signed(extra >> 16, 16) * 2,
                             condition={"register": register, "comparison": comparison, "immediate": constant, "signed": signed})
        instruction["text"] = f"if {register} {comparison} {constant}: " + instruction["text"]
        return instruction
    if word & 0xFFF0 in (0xFFC0, 0xFFE0):
        register = f"r{ra}" if word & 0xFFF0 == 0xFFC0 else SPECIAL_REGISTERS[ra]
        return emit("mov", f"{register} = 0x{extra:08x}", register=register, immediate=extra)
    if width == 6:
        return result
    if width == 4 and word >> 8 in (0xF8, 0xF9, 0xFC, 0xFD, 0xFE):
        family = word >> 8
        second = bool(word & 0x80)
        comparison = {0xF8: ("==", "!="), 0xF9: (">=", "<"), 0xFC: (">", "<="),
                      0xFD: (">=", "<"), 0xFE: (">", "<=")}[family][second]
        signed = family in (0xF8, 0xFD, 0xFE)
        immediate = ((word >> 4 & 7) << 7) | (extra >> 9)
        if signed:
            immediate = _signed(immediate, 10)
        register = f"r{ra}"
        instruction = branch("branch_if", _signed(extra & 0x1FF, 9) * 2,
                             condition={"register": register, "comparison": comparison, "immediate": immediate, "signed": signed})
        instruction["text"] = f"if {register} {comparison} {immediate}: " + instruction["text"]
        return instruction
    if width == 4 and word & 0xFFF0 in (0xED80, 0xEE00) and not extra & 0xE00:
        comparison = "<" if word & 0xFFF0 == 0xED80 else ">"
        left, right = f"r{extra >> 12}", f"r{ra}"
        instruction = branch("branch_if", _signed(extra & 0x1FF, 9) * 2,
                             condition={"register": left, "comparison": comparison, "other_register": right, "signed": True})
        instruction["text"] = f"if {left} {comparison} {right}: " + instruction["text"]
        return instruction
    if group == 4 and w & 0x8F == 1:
        return branch("call", (_signed(w >> 4 & 7, 3) << 6) | ((w >> 8 & 31) << 1))
    if group == 7 and (w >> 6 & 0x7F) in (0x2A, 0x2B):
        return branch("call" if w >> 6 & 0x7F == 0x2A else "goto", (_signed(w & 63, 6) << 17) | (extra << 1))
    if group == 4 and w >> 2 & 3 == 1:
        return branch("goto", (_signed(w & 3, 2) << 10) | ((w >> 4 & 15) << 6) | ((w >> 8 & 31) << 1))
    if group == 2 and not w & 8:
        return branch("jnz" if w & 0x80 else "jz", (_signed(w >> 4 & 7, 3) << 6) | ((w >> 8 & 31) << 1), register=f"r{a}")
    if group == 0 and w in (0, 1, 2, 3, 0x20, 0x21, 0x22, 0x23, 0x40, 0x41, 0x60, 0x61, 0x80, 0x81, 0x82, 0x83):
        name = {0: "nop", 1: "idle", 2: "bkpt", 3: "hbkpt", 0x20: "csync", 0x21: "syscall", 0x22: "ssync", 0x23: "btbclr", 0x40: "lockclr", 0x41: "lockset", 0x60: "cli", 0x61: "sti", 0x80: "rts", 0x81: "rti", 0x82: "rtx", 0x83: "rte"}[w]
        return emit(name, name)
    if group == 0 and w & 0xFFF0 in (0xC0, 0xD0, 0x100):
        name = {0xC0: "call_indirect", 0xD0: "goto_indirect", 0x100: "tbb"}[w & 0xFFF0]
        return emit(name, f"{name} r{ra}", register=f"r{ra}", target=None)
    if group == 0 and w == 0x400:
        return emit("pop_pc", "pop pc")
    if group == 0 and w == 0x410:
        return emit("push", "push rets", registers=["rets"])
    if group == 0 and w & 0xFFF0 in (0x430, 0x440, 0x450, 0x460, 0x470):
        top = w & 0xFFF0
        registers = (["pc"] if top == 0x450 else ["rets"] if top in (0x430, 0x470) else []) + [f"r{i}" for i in (range(ra, 3, -1) if ra >= 4 else range(3, ra - 1, -1))]
        name = "push" if top in (0x460, 0x470) else "pop_pc" if top == 0x450 else "pop"
        return emit(name, name + " {" + ", ".join(registers) + "}", registers=registers)
    if group == 0 and w >> 8 == 0x16:
        return emit("mov", f"r{ra} = r{rb}", register=f"r{ra}", source_register=f"r{rb}")
    if group == 0 and w >> 7 in (0x2E, 0x2F):
        name = (("uxtb", "sxtb"), ("uxth", "sxth"))[w >> 7 == 0x2F][bool(w & 8)]
        return emit(name, f"{name} r{a}, r{b}", register=f"r{a}", source_register=f"r{b}")
    if group == 0 and w >> 8 in (0x18, 0x1B):
        name = {0x18: "add", 0x1B: "mul"}[w >> 8]
        return emit(name, f"{name} r{ra}, r{rb}", register=f"r{ra}", source_register=f"r{rb}")
    if group == 0 and w >> 7 in (0x32, 0x33):
        name = (("or", "xor"), ("and", "not"))[w >> 7 == 0x33][bool(w & 8)]
        return emit(name, f"{name} r{a}, r{b}", register=f"r{a}", source_register=f"r{b}")
    if group == 0 and w >> 7 in (0x34, 0x35):
        name = (("lsl", "qasl"), ("lsr", "asr"))[w >> 7 == 0x35][bool(w & 8)]
        return emit(name, f"{name} r{a}, r{b}", register=f"r{a}", source_register=f"r{a}", shift_register=f"r{b}")
    if group == 0 and w >> 9 in (0xE, 0xF):
        c = (w >> 7 & 3) * 2 + (w >> 3 & 1)
        name = "add" if w >> 9 == 0xE else "sub"
        return emit(name, f"r{a} = r{b} {'+' if name == 'add' else '-'} r{c}", register=f"r{a}", source_registers=[f"r{b}", f"r{c}"])
    if group == 1:
        mode = w >> 6 & 3
        immediate = ((w >> 3 & 7) << 5) | (w >> 8 & 31)
        if mode in (0, 2):
            if mode == 0 and w & 0x38 == 0x10:
                immediate = (w >> 8 & 31) - 32
                return emit("mov", f"r{a} = {immediate}", register=f"r{a}", immediate=immediate)
            if w & 0xF8 in (0x30, 0x38, 0xB8):
                name = {0x30: "or", 0x38: "xor", 0xB8: "and"}[w & 0xF8]
                immediate = 1 << (w >> 8 & 31)
                if name == "and":
                    immediate = (~immediate) & 0xFFFFFFFF
                return emit(name, f"{name} r{a}, 0x{immediate:x}", register=f"r{a}", source_register=f"r{a}", immediate=immediate)
            if w & 0x38:
                return result  # Other short immediates/bit operations, not SP loads.
            return memory("sw" if mode == 2 else "lw", f"r{a}", "sp", immediate * 4, 4)
        if mode == 1:
            return emit("mov", f"r{a} = {immediate}", register=f"r{a}", immediate=immediate)
        immediate = _signed(immediate, 8)
        return emit("add", f"r{a} += {immediate}", register=f"r{a}", immediate=immediate)
    if group == 4 and w & 31 == 2:
        immediate = (_signed(w >> 5 & 7, 3) << 7) | ((w >> 8 & 31) << 2)
        return emit("add", f"sp += {immediate}", register="sp", immediate=immediate)
    if group == 4 and w & 0x88 == 8:
        immediate = w >> 8 & 31
        return emit("add", f"r{a} = r{b} + {immediate}", register=f"r{a}", source_register=f"r{b}", immediate=immediate)
    if group == 4 and w & 0x98 == 0x88:
        immediate = ((w >> 5 & 3) << 5) | (w >> 8 & 31)
        return emit("add", f"r{a} = sp + {immediate}", register=f"r{a}", source_register="sp", immediate=immediate)
    if group == 5:
        kind = {(0, 0): "lsl", (0, 1): "qasl", (1, 0): "lsr", (1, 1): "asr"}[(w >> 7 & 1, w >> 3 & 1)]
        immediate = w >> 8 & 31
        if not immediate:
            return result  # Zero shift encodings need separate ISA verification.
        return emit(kind, f"{kind} r{a}, r{b}, {immediate}", register=f"r{a}", source_register=f"r{b}", immediate=immediate)
    if group == 0 and w >> 7 in range(0xA, 0x10):
        op = w >> 7
        access_size = (4, 4, 2, 2, 1, 1)[op - 0xA]
        name = ("lw", "sw", "lhu", "sh", "lbu", "sb")[op - 0xA]
        delta = -access_size if w & 8 else access_size
        return memory(name, f"r{a}", f"r{b}", 0, access_size, f"post {delta:+d}")
    if group == 3 or (group == 2 and w & 8):
        access_size = 1 if group == 2 else 2 if w & 8 else 4
        store = bool(w & 0x80)
        name = {1: ("lbu", "sb"), 2: ("lhu", "sh"), 4: ("lw", "sw")}[access_size][store]
        return memory(name, f"r{a}", f"r{b}", _signed(w >> 8 & 31, 5) * access_size, access_size)
    if width == 4 and w & 0xEFF0 == 0xE040:
        immediate = _signed(extra, 16)
        return emit("mov", f"r{ra} = {immediate}", register=f"r{ra}", immediate=immediate, parallel_pair=bool(w & 0x1000))
    if width == 4 and w & 0xEFFF == 0xE060:
        immediate = compact_immediate(extra & 0xFFF)
        return emit("mov", f"r{extra >> 12} = 0x{immediate:x}", register=f"r{extra >> 12}", immediate=immediate, parallel_pair=bool(w & 0x1000))
    if width == 4 and w & 0xEFFF == 0xE064 and extra & 0xFF == 0:
        destination, source = f"r{extra >> 12}", SPECIAL_REGISTERS[extra >> 8 & 15]
        return emit("mov", f"{destination} = {source}", register=destination, source_register=source, parallel_pair=bool(w & 0x1000))
    if width == 4 and w & 0xEFF0 in (0xE0A0, 0xE0E0, 0xE0F0, 0xE140, 0xE150, 0xE160, 0xE170, 0xE1E0):
        kind = {0xE0A0: "reverse_sub", 0xE0E0: "add", 0xE0F0: "sub", 0xE140: "or", 0xE150: "xor", 0xE160: "and", 0xE170: "and_not", 0xE1E0: "mul"}[w & 0xEFF0]
        immediate = compact_immediate(extra & 0xFFF)
        return emit(kind, f"{kind} r{ra}, r{extra >> 12}, 0x{immediate:x}", register=f"r{ra}", source_register=f"r{extra >> 12}",
                    immediate=immediate, parallel_pair=bool(w & 0x1000), immediate_encoding="compact12")
    if width == 4 and w & 0xEFFF == 0xE0B4 and extra & 15 == 0:
        destination, left, right = extra >> 12, extra >> 4 & 15, extra >> 8 & 15
        return emit("add", f"r{destination} = r{left} + r{right}", register=f"r{destination}", source_registers=[f"r{left}", f"r{right}"], parallel_pair=bool(w & 0x1000))
    if width == 4 and w & 0xEFFF == 0xE1C0 and not extra & 0x200:
        immediate = (extra & 15) | ((extra >> 4) & 16)
        if immediate == 0:
            immediate = 32
        kind = ("lsl", "qasl", "lsr", "asr")[extra >> 10 & 3]
        destination, source = f"r{extra >> 12}", f"r{extra >> 4 & 15}"
        return emit(kind, f"{kind} {destination}, {source}, {immediate}", register=destination, source_register=source,
                    immediate=immediate, parallel_pair=bool(w & 0x1000))
    if width == 4 and w & 0xEFFF == 0xE1C8 and not extra & 12:
        kind = ("lsl", "qasl", "lsr", "asr")[extra & 3]
        destination, source, shift = f"r{extra >> 12}", f"r{extra >> 4 & 15}", f"r{extra >> 8 & 15}"
        return emit(kind, f"{kind} {destination}, {source}, {shift}", register=destination, source_register=source,
                    shift_register=shift, parallel_pair=bool(w & 0x1000))
    if width == 4 and w & 0xEFF0 == 0xE1B0 and not extra & 2 and extra >> 2 & 31:
        position, length = extra >> 7 & 31, extra >> 2 & 31
        name = "sextra" if extra & 1 else "uextra"
        return emit(name, f"{name} r{ra}, r{extra >> 12}, {position}, {length}",
                    register=f"r{ra}", source_register=f"r{extra >> 12}", position=position,
                    length=length, parallel_pair=bool(w & 0x1000))
    if width == 4 and w & 0xFFF0 in (0xE8B0, 0xED30, 0xEEB0) and extra & 0xF000 == 0:
        comparison = {0xE8B0: "!=", 0xED30: ">=", 0xEEB0: "<="}[w & 0xFFF0]
        immediate = _signed(extra & 0xFFF, 12)
        predicate = {"register": f"r{ra}", "comparison": comparison, "immediate": immediate,
                     "signed": comparison != "!=", "instruction_count": 1}
        return emit("predicate_next", f"if r{ra} {comparison} {immediate}: next instruction", predicate=predicate,
                    scope="one following instruction; paired companions require separate validation")
    if width == 4 and w & 0xFFF0 == 0xEE90 and extra & 0xF0FF == 0:
        left, right = f"r{ra}", f"r{extra >> 8 & 15}"
        return emit("predicate_next", f"if {left} <= {right}: next instruction",
                    predicate={"register": left, "comparison": "<=", "other_register": right, "signed": True, "instruction_count": 1},
                    scope="one following instruction; paired companions require separate validation")
    if width == 4 and w & 0xEFFE == 0xE434 and extra & 14 == 0:
        name = ("s" if extra & 1 else "u") + ("min" if w & 1 else "max")
        destination, left, right = f"r{extra >> 12}", f"r{extra >> 4 & 15}", f"r{extra >> 8 & 15}"
        return emit(name, f"{destination} = {name}({left}, {right})", register=destination, source_registers=[left, right],
                    parallel_pair=bool(w & 0x1000))
    if width == 4 and w & 0xEFC0 == 0xE100:
        immediate = _signed(((w & 0x30) << 8) | (extra & 0xFFF), 14)
        return emit("add", f"r{ra} = r{extra >> 12} + {immediate}", register=f"r{ra}",
                    source_register=f"r{extra >> 12}", immediate=immediate, parallel_pair=bool(w & 0x1000))
    if width == 4 and w & 0xEFFF == 0xE190 and extra & 15 in (0, 1, 2, 3):
        name = ("or", "xor", "and", "and_not")[extra & 15]
        destination, left, right = extra >> 12, extra >> 4 & 15, extra >> 8 & 15
        return emit(name, f"{name} r{destination}, r{left}, r{right}", register=f"r{destination}",
                    source_registers=[f"r{left}", f"r{right}"], parallel_pair=bool(w & 0x1000))
    # Extended word offsets were independently checked against the vendor
    # listing. Bit 1 in the low nibble means a pre-update of the base register.
    if width == 4 and w & 0xFFF8 == 0xECD0:
        offset = _signed(((w & 7) << 8) | ((extra >> 4) & 0xF0) | (extra & 12), 11)
        return memory("sw" if extra & 1 else "lw", f"r{extra >> 12}", f"r{extra >> 4 & 15}", offset, 4, "pre" if extra & 2 else None)
    if width == 4 and w & 0xFFF8 == 0xECD8 and not extra & 2:
        offset = _signed(((w & 7) << 8) | ((extra >> 4) & 0xF0) | (extra & 12), 11)
        return memory("sw" if extra & 1 else "lw", f"r{extra >> 12}", f"r{extra >> 4 & 15}", 0, 4, f"post {offset:+d}")
    if width == 4 and w & 0xFFFC == 0xEE50:
        offset = _signed(((w & 1) << 8) | ((extra >> 4) & 0xF0) | (extra & 15), 9)
        return memory("sb" if w & 2 else "lbu", f"r{extra >> 12}", f"r{extra >> 4 & 15}", offset, 1)
    if width == 4 and (w, extra & 14) in ((0xECD8, 10), (0xEDD8, 8), (0xEED8, 0)):
        access_size = {0xECD8: 4, 0xEDD8: 2, 0xEED8: 1}[w]
        store = bool(extra & 1)
        name = {4: ("lw", "sw"), 2: ("lhu", "sh"), 1: ("lbu", "sb")}[access_size][store]
        register, base, index = f"r{extra >> 12}", f"r{extra >> 4 & 15}", f"r{extra >> 8 & 15}"
        shift = {4: 2, 2: 1, 1: 0}[access_size]
        return emit(name, f"{name} {register}, [{base}+{index}<<{shift}]", register=register,
                    memory={"base": base, "offset": None, "index": index, "index_shift": shift,
                            "width": access_size, "access": "write" if store else "read", "update": None})
    return result


def _v15_layout(blob: bytes) -> bool:
    # CRT bytes prove copy/zero bounds; literal-to-string pairs independently
    # prove the XIP base. These anchors also allow a locally edited application
    # to retain a map if none of the map-defining evidence has changed.
    return (len(blob) == 581564 and _sha(blob[:198]) == _V15_FUNCTIONS[0][3]
            and all(blob[p:p + 6] == bytes.fromhex(code) and blob[q:q + len(text)] == text
                    for p, code, q, text in (
                        (0x2A054, "c1ff6ce70402", 0x4E64C, b"EXT_RESERVED\0"),
                        (0x2A376, "c5ffafe70402", 0x4E68F, b"app_area_head\0"),
                        (0x284FC, "c1ff86e70402", 0x4E666, b"audio_server\0"))))


def _address(offset: int, mapped: bool) -> int | None:
    if not mapped:
        return None
    if RAM_FILE_OFFSET <= offset < RAM_FILE_OFFSET + RAM_SIZE:
        return RAM_BASE + offset - RAM_FILE_OFFSET
    if 0 <= offset < RAM_FILE_OFFSET:
        return XIP_BASE + offset
    return None


def address_to_offset(address: int, analysis: dict) -> int | None:
    """Resolve a proven runtime region; BSS has no file bytes."""
    for region in analysis.get("regions", []):
        base, start = region.get("runtime_address"), region.get("file_offset")
        if base is not None and start is not None and base <= address < base + region["size"]:
            return start + address - base
    return None


def disassemble(blob: bytes, start: int = 0, size: int | None = None, *, analysis: dict | None = None) -> dict:
    """Bounded linear decode with explicit boundary/coverage limitations."""
    _validate(blob)
    if not isinstance(start, int) or start < 0 or start >= len(blob):
        raise DecodeError("disassembly offset lies outside application")
    if size is None:
        size = min(len(blob) - start, 4096)
    if (not isinstance(start, int) or not isinstance(size, int) or start < 0 or size < 1
            or start > len(blob) or size > len(blob) - start or size > MAX_DISASSEMBLY_BYTES):
        raise DecodeError(f"disassembly must be within the image and at most {MAX_DISASSEMBLY_BYTES} bytes")
    mapped = _v15_layout(blob)
    inline_tables = []
    note = _V15_FUNCTIONS[3]
    if mapped and _sha(blob[note[1]:note[1] + note[2]]) == note[3]:
        inline_tables = [(0x85BB4, 6), (0x860D6, 4)]
    rows = []
    offset = start
    bounded_blob = blob[:start + size]
    while offset < start + size:
        table = next(((p, count) for p, count in inline_tables if p <= offset < p + count), None)
        if table:
            table_start, count = table
            end = min(table_start + count, start + size)
            raw = blob[offset:end]
            rows.append({"file_offset": offset, "address": _address(offset, mapped), "size": len(raw),
                         "bytes": raw.hex(), "mnemonic": "jump_table", "text": "TBB byte offsets " + raw.hex(),
                         "supported": False, "is_data": True,
                         "targets": [_address(table_start + 2 * value, mapped) for value in raw]})
            offset = end
            continue
        # Slice at the requested boundary; no instruction reads past it.
        instruction = decode_instruction(bounded_blob, offset, _address(offset, mapped))
        rows.append(instruction)
        offset += instruction["size"]
    supported = sum(r["size"] for r in rows if r["supported"])
    data_bytes = sum(r["size"] for r in rows if r.get("is_data"))
    for index, row in enumerate(rows[:-1]):
        if row.get("parallel_pair"):
            row["packet_file_offset"] = row["file_offset"]
            rows[index + 1]["packet_file_offset"] = row["file_offset"]
            rows[index + 1]["parallel_companion"] = True
    return {"kind": "pi32v2-linear-disassembly", "start": start, "size": size,
            "instructions": rows, "supported_bytes": supported, "data_bytes": data_bytes,
            "unsupported_bytes": size - supported - data_bytes,
            "boundary_verified": mapped and any(offset == start and _sha(blob[offset:offset + count]) == fingerprint
                                                  for _, offset, count, fingerprint, *_ in _V15_FUNCTIONS),
            "limitations": ["Linear decoding can interpret embedded tables as instructions.",
                            "Unsupported opcodes are retained as bytes; this is not complete disassembly or emulation."]}


def _strings(blob: bytes, mapped: bool) -> tuple[list[dict], bool]:
    rows = []
    for match in re.finditer(rb"[\x20-\x7e]+", blob):
        length = match.end() - match.start()
        if not 5 <= length <= 512 or match.end() == len(blob) or blob[match.end()] != 0:
            continue
        raw = match.group()
        # Long printable numeric tables and run padding are poor strings.
        if not re.search(rb"[A-Za-z]{3}", raw):
            continue
        text = raw.decode("ascii")
        category = "identity" if re.search(r"FM-1_[0-9]{3}", text) else "audio" if re.search(r"audio|midi|synth|reverb|chorus|effect|sample|pitch|voice|dac|adc", text, re.I) else "system"
        rows.append({"text": text, "file_offset": match.start(), "address": _address(match.start(), mapped), "category": category})
        if len(rows) == MAX_STRINGS:
            return rows, True
    return rows, False


def analyze_control_flow(blob: bytes, start: int, size: int, *, analysis: dict | None = None) -> dict:
    """Explore possible paths inside one bounded span; unknown semantics stop a path.

    This is a static graph, not a proof of execution. Calls have a potential
    continuation edge; no callee return behavior or register values are assumed.
    """
    listing = disassemble(blob, start, size, analysis=analysis)
    rows = listing["instructions"]
    by_offset = {row["file_offset"]: row for row in rows}
    mapped = _v15_layout(blob)
    pending, visited, edges, barriers = [start], set(), [], []
    def target_offset(row: dict) -> int | None:
        target = row.get("target")
        if mapped and target is not None:
            if XIP_BASE <= target < XIP_BASE + RAM_FILE_OFFSET:
                return target - XIP_BASE
            if RAM_BASE <= target < RAM_BASE + RAM_SIZE:
                return target - RAM_BASE + RAM_FILE_OFFSET
            return None
        if not mapped and "displacement" in row:
            return row["file_offset"] + row["size"] + row["displacement"]
        return None
    def edge(source: int, target: int | None, kind: str) -> None:
        inside = target is not None and start <= target < start + size
        valid = inside and target in by_offset and not by_offset[target].get("is_data")
        edges.append({"source_file_offset": source, "target_file_offset": target,
                      "kind": kind, "within_span": inside, "instruction_boundary": bool(valid)})
        if valid:
            if target not in visited:
                pending.append(target)
        elif inside:
            barriers.append({"file_offset": source, "reason": "target is not a decoded instruction boundary", "target_file_offset": target})
    while pending:
        offset = pending.pop()
        if offset in visited:
            continue
        visited.add(offset)
        row = by_offset[offset]
        following = offset + row["size"]
        name = row["mnemonic"]
        if not row["supported"]:
            barriers.append({"file_offset": offset, "reason": "unsupported instruction or inline data"})
            continue
        if name in ("rts", "rti", "rtx", "rte", "pop_pc", "idle", "bkpt", "hbkpt"):
            continue
        if name in ("goto", "gotoss"):
            edge(offset, target_offset(row), "jump")
        elif name in ("branch_if", "jz", "jnz"):
            edge(offset, target_offset(row), "condition true")
            edge(offset, following, "condition false")
        elif name == "predicate_next":
            predicated = by_offset.get(following)
            if predicated is None or predicated.get("parallel_pair") or predicated.get("is_data"):
                barriers.append({"file_offset": offset, "reason": "predicate scope over a packet or truncated span is unverified"})
                continue
            edge(offset, following, "predicate true")
            edge(offset, following + predicated["size"], "predicate false")
        elif name == "tbb":
            table = by_offset.get(following)
            if table is None or not table.get("is_data"):
                barriers.append({"file_offset": offset, "reason": "jump table is not independently identified"})
                continue
            for value in bytes.fromhex(table["bytes"]):
                edge(offset, following + 2 * value, "table branch")
        elif name in ("goto_indirect",):
            barriers.append({"file_offset": offset, "reason": "indirect jump target is unknown"})
        elif name in ("call", "call_indirect"):
            if name == "call":
                edge(offset, target_offset(row), "call")
            else:
                barriers.append({"file_offset": offset, "reason": "indirect call target is unknown"})
            edge(offset, following, "possible call continuation")
        else:
            edge(offset, following, "packet companion" if row.get("parallel_pair") else "fallthrough")
    return {"kind": "bounded-static-control-flow", "start": start, "size": size,
            "boundary_verified": listing["boundary_verified"],
            "nodes": [{"file_offset": offset, "address": by_offset[offset]["address"], "mnemonic": by_offset[offset]["mnemonic"]} for offset in sorted(visited)],
            "edges": edges, "barriers": barriers,
            "possible_reached_bytes": sum(by_offset[offset]["size"] for offset in visited),
            "limitations": ["Edges are static possibilities, not observed execution.",
                            "Unsupported instructions stop a path; register values and predicate truth are not simulated.",
                            "Callee return behavior, interrupt entry and unknown indirect destinations remain unresolved."]}


def analyze_application(blob: bytes) -> dict:
    """Analyze extracted app bytes without device access or external programs."""
    _validate(blob)
    sha = _sha(blob)
    mapped = _v15_layout(blob)
    strings, truncated = _strings(blob, mapped)
    package_report = inspect_application(blob)
    report = {"schema_version": 1, "kind": "fm1-executable-analysis", "size": len(blob), "sha256": sha,
              "identities": package_report["embedded_identities"],
              "profile": {"name": "FM-1_015" if mapped else "unrecognized application",
                          "matched": mapped, "exact_image": sha == V15_SHA256,
                          "confidence": "verified startup and address anchors" if mapped else "unknown"},
              "regions": [], "functions": [], "calls": [], "features": [], "dsp": {},
              "strings": strings, "strings_truncated": truncated,
              "unresolved": ["The complete instruction set, indirect calls and interrupt entry graph are not decoded.",
                             "Names inherited from prior firmware analysis are hypotheses, not recovered symbols.",
                             "No source reconstruction, audio equivalence, safe write procedure or device behavior is proven."],
              "device_io_performed": False}
    if mapped:
        report["regions"] = [
            {"name": "flash application body", "file_offset": 0, "size": RAM_FILE_OFFSET,
             "runtime_address": XIP_BASE, "permissions": "mixed code and read-only data",
             "evidence": "Three absolute mov/string pairs prove base 0x02000120; CRT copies RAM image from 0x02084060."},
            {"name": "RAM initialization image", "file_offset": RAM_FILE_OFFSET, "size": RAM_SIZE,
             "runtime_address": RAM_BASE, "xip_address": XIP_BASE + RAM_FILE_OFFSET,
             "permissions": "mixed executable code and writable data",
             "evidence": "CRT at file 0x2c/0x32/0x38 copies 0xa05c bytes to 0x01c00000."},
            {"name": "zero-initialized RAM (BSS)", "file_offset": None, "size": 0x195C0,
             "runtime_address": 0x01C0A05C, "permissions": "read/write; no bytes in application",
             "evidence": "CRT mov instructions at file 0x16/0x1e and zero loop at 0x24."},
            {"name": "application trailer", "file_offset": RAM_FILE_OFFSET + RAM_SIZE,
             "size": len(blob) - RAM_FILE_OFFSET - RAM_SIZE, "runtime_address": None,
             "permissions": "unclassified data", "evidence": "32 bytes remain beyond the CRT copy extent."},
        ]
        for name, offset, size, fingerprint, category, confidence, reference in _V15_FUNCTIONS:
            if _sha(blob[offset:offset + size]) != fingerprint:
                report["unresolved"].append(f"The {name} fingerprint changed; its semantic annotation was withheld.")
                continue
            row = {"name": name, "file_offset": offset, "address": _address(offset, True), "size": size,
                   "sha256": fingerprint, "category": category, "confidence": confidence,
                   "evidence": "Fresh V15 byte fingerprint; explicit function entry and terminating return.",
                   "reference_file_offset": reference}
            if reference is not None:
                row["evidence"] += " Role inferred from V009 instruction-block similarity; function bytes differ across versions."
                row["reference_image_sha256"] = V009_SHA256
            if name == "envelope_update_candidate":
                row["evidence"] += " V009 matches 204/208 bytes; differences are the data-base immediate and level-table displacement. Fresh state accesses, arithmetic and MSFA comparison are documented in docs/20-envelope-decoding.md."
            decoded = disassemble(blob, offset, size)
            row["supported_bytes"] = decoded["supported_bytes"]
            row["unsupported_bytes"] = decoded["unsupported_bytes"]
            row["inline_data_bytes"] = decoded["data_bytes"]
            report["functions"].append(row)
            row["control_flow"] = analyze_control_flow(blob, offset, size, analysis=report)
            for ins in decoded["instructions"]:
                if ins["mnemonic"] in ("call", "call_indirect"):
                    report["calls"].append({"source": ins["address"], "target": ins.get("target"),
                                            "source_file_offset": ins["file_offset"], "function": name,
                                            "target_file_offset": address_to_offset(ins["target"], report) if ins.get("target") is not None else None,
                                            "register": ins.get("register"), "bytes": ins["bytes"],
                                            "evidence": "Decoded instruction in a fingerprinted span; reachability and indirect target remain unproven."})
        named_targets = {function["file_offset"]: function for function in report["functions"]}
        for call in report["calls"]:
            target = named_targets.get(call["target_file_offset"])
            call["target_function"] = target["name"] if target else None
            call["target_confidence"] = target["confidence"] if target else None
        report["address_proof"] = [{"file_offset": off, "bytes": blob[off:off + 6].hex(), "target_file_offset": target,
                                     "target_address": XIP_BASE + target, "text": text}
                                    for off, target, text in ((0x2A054, 0x4E64C, "EXT_RESERVED"), (0x2A376, 0x4E68F, "app_area_head"), (0x284FC, 0x4E666, "audio_server"))]
    else:
        report["regions"] = [{"name": "unmapped application bytes", "file_offset": 0, "size": len(blob),
                              "runtime_address": None, "permissions": "unknown", "evidence": "No supported startup/address profile matched."}]
        report["unresolved"].append("Runtime addresses and function names are withheld without the supported startup/address profile.")
    tables = [{**table, "file_offset": table["offset"], "address": _address(table["offset"], mapped)} for table in package_report["msfa_tables"]]
    report["dsp"] = {"algorithm_tables": tables,
                     "mathematical_tables": analyze_dsp_tables(blob, report["regions"]),
                     "effects": analyze_effects(blob),
                     "sound_equivalence_proven": False,
                     "evidence": "Algorithm-table byte matches establish data lineage, not complete DSP equivalence."}
    # The confirmed table location is independently searched by the package
    # inspector; no version label is used to guess a table offset.
    for item in strings:
        if item["category"] in ("identity", "audio"):
            report["features"].append({"name": item["text"], "category": item["category"],
                                       "locations": [{"file_offset": item["file_offset"], "address": item["address"]}],
                                       "confidence": "verified string only", "evidence": "NUL-terminated printable bytes; execution is not established."})
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("application", type=Path)
    parser.add_argument("--offset", type=lambda value: int(value, 0), help="linear disassembly file offset")
    parser.add_argument("--size", type=lambda value: int(value, 0), default=4096, help="disassembly byte count (maximum 65536)")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.application.stat().st_size > MAX_INPUT_SIZE:
            raise DecodeError("application exceeds input size limit")
        blob = args.application.read_bytes()
        report = analyze_application(blob)
        if args.offset is not None:
            report = disassemble(blob, args.offset, args.size, analysis=report)
        text = json.dumps(report, indent=2) + "\n"
        if args.output:
            if args.output.resolve() == args.application.resolve():
                raise DecodeError("analysis output must not overwrite the source application")
            args.output.write_text(text, encoding="utf-8")
        else:
            print(text, end="")
    except (OSError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    main()
