#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Strict final-link audit for calls reachable from the FM-1 RAM section."""
import re

_EXPECTED_CALLER = "fl_jedec_ram"
_EXPECTED_TARGET = "fl_jedec_checked_ram"


def audit_ram_call_allowlist(disassembly, symbols):
    """Allow only the checked JEDEC helper call at its linked RAM address.

    Both the call-site and target must be attributed in the final .ram_text
    section. Empty, ambiguous, malformed, indirect, or additional calls fail.
    """
    symbol_rows = {}
    symbol_pattern = re.compile(
        r"^\s*([0-9a-fA-F]+)\s+\S+\s+F\s+\.ram_text\s+"
        r"([0-9a-fA-F]+)\s+(\S+)\s*$", re.MULTILINE)
    for match in symbol_pattern.finditer(symbols):
        address, size, name = match.groups()
        if name in symbol_rows:
            raise ValueError(f"duplicate RAM symbol: {name}")
        symbol_rows[name] = (int(address, 16), int(size, 16))

    for name in (_EXPECTED_CALLER, _EXPECTED_TARGET):
        if name not in symbol_rows:
            raise ValueError(f"missing RAM symbol: {name}")
        if symbol_rows[name][1] == 0:
            raise ValueError(f"empty RAM symbol: {name}")

    current = None
    seen_labels = set()
    instruction_count = 0
    calls = []
    for line in disassembly.splitlines():
        label = re.fullmatch(r"([A-Za-z_.$][A-Za-z0-9_.$@-]*):", line.strip())
        if label:
            current = label.group(1)
            if current in seen_labels:
                raise ValueError(f"duplicate RAM disassembly label: {current}")
            seen_labels.add(current)
            continue
        instruction = re.match(r"^\s*([0-9a-fA-F]+):\s+.*$", line)
        if instruction:
            instruction_count += 1
            if re.search(r"\bcall\b", line):
                if current is None:
                    raise ValueError("RAM call has no containing function label")
                # Require the target annotation emitted by the pinned objdump;
                # unresolved/indirect calls are intentionally not allowlisted.
                target = re.search(r"\bcall\b[^<]*<\s*([^<>:]+?)\s*:\s*([0-9a-fA-F]+)\s*>", line)
                if target is None:
                    raise ValueError(f"malformed or indirect RAM call in {current}")
                calls.append({"caller": current,
                              "site": int(instruction.group(1), 16),
                              "target": target.group(1).strip(),
                              "target_address": int(target.group(2), 16),
                              "instruction": line.strip()})
        elif re.search(r"\bcall\b", line):
            raise ValueError("malformed RAM call instruction without an address")

    if instruction_count == 0:
        raise ValueError("RAM disassembly contains no instructions")
    for name in (_EXPECTED_CALLER, _EXPECTED_TARGET):
        if name not in seen_labels:
            raise ValueError(f"missing RAM disassembly label: {name}")

    expected_address = symbol_rows[_EXPECTED_TARGET][0]
    if len(calls) != 1:
        raise ValueError(f"expected exactly one allowlisted RAM call, found {len(calls)}")
    call = calls[0]
    if call["caller"] != _EXPECTED_CALLER:
        raise ValueError(f"unexpected RAM call caller: {call['caller']}")
    if call["target"] != _EXPECTED_TARGET:
        raise ValueError(f"unexpected RAM call target: {call['target']}")
    if call["target_address"] != expected_address:
        raise ValueError("RAM call target address does not match linked symbol")
    return {"passed": True, "allowed_calls": calls,
            "required_symbols": {name: {"address": symbol_rows[name][0],
                                        "size": symbol_rows[name][1]}
                                 for name in (_EXPECTED_CALLER, _EXPECTED_TARGET)}}
