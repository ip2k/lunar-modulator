"""Pure offline decoding of retained USB_KEY receipts; no device access."""


def decode_terminal(registers):
    """Decode integer-address words, preserving legacy transient semantics.

    Candidate means a local FSM observation, never confirmed target/ROM ACK.
    A pre-terminal or legacy receipt cannot establish persistent absence.
    """
    if registers[1] != 0x4C554E52 or registers[2] not in (7, 8, 9):
        raise ValueError('Unsupported USB_KEY magic/layout')
    valid = bool(registers[0x0c] & 1)
    progress = registers[0x0e]
    candidate = None
    if registers[2] == 9:
        receipt = registers[0x67]
        if receipt & ~3 or bool(receipt & 1) != valid:
            raise ValueError('Invalid or inconsistent candidate receipt')
        if valid:
            candidate = bool(receipt & 2)
    return dict(layout=registers[2], terminal_valid=valid,
                receiver_live=bool(progress & 1),
                transient_ack_predicate=bool(progress & 2),
                ack_ticks_us=(progress >> 2) & 0xffff,
                local_ack_candidate=candidate,
                key_phase_us=(registers[0x12] >> 8) & 0xffff)
