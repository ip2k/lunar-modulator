# SPDX-License-Identifier: MIT
"""Opt-in, stack-free entry instrumentation for timed native probes."""
import re

PAINTER_BYTES = bytes.fromhex(
    'c1ff0041c701 c2ff00a0c701 c3ff5aa55aa5 9360 1984 82e8fc11 '
    'c1ff00a1c701 c2ff00c0c701 9360 1984 82e8fc11')


def verify_instrumentation(image, disassembly):
    """Check actual target stores/loops and both call targets against ELF bytes."""
    begin = image.symbol_value('lunar_stack_watermark_begin')
    end = image.symbol_value('lunar_stack_watermark_end')
    if end != begin + len(PAINTER_BYTES) or image.read(begin, len(PAINTER_BYTES)) != PAINTER_BYTES:
        raise ValueError('Stack painter bytes/ranges differ from reviewed bounded loops')
    if image.read(0x02000158, 12) != bytes.fromhex('eeff00a0c701 edff00c0c701'):
        raise ValueError('Stack setup before painter differs')
    calls = []
    for pc, symbol, target in ((0x02000164, 'lunar_stack_watermark_begin', begin),
                               (end, 'fm1_cstart', image.symbol_value('fm1_cstart'))):
        match = re.search(r'^\s*' + format(pc, 'x') +
                          r':\s+((?:[0-9a-f]{2} )+)\s*call [^\n]*<' + symbol +
                          r' : ' + format(target, 'x') + r' >\s*$',
                          disassembly, re.M)
        if not match:
            raise ValueError('Missing compiled stack painter call: ' + symbol)
        opcode = bytes.fromhex(match.group(1))
        if len(opcode) != 4 or image.read(pc, 4) != opcode:
            raise ValueError('Stack painter call does not match ELF bytes')
        calls.append(dict(pc=pc, target=target, symbol=symbol, opcode=opcode.hex()))
    return dict(pattern=0xA55AA55A, painter_begin=begin, painter_end=end,
                painter_bytes=PAINTER_BYTES.hex(), calls=calls,
                user_bytes=24320, system_bytes=7936, hardware_tested=False,
                worst_case_stack_bound=False)


def instrument_entry(source):
    anchor = '\tcall fm1_cstart\n'
    if source.count(anchor) != 1 or 'lunar_stack_watermark_begin' in source:
        raise ValueError('Pinned stack watermark entry adaptation no longer matches')
    # Preserve the entry guard/rejected-loop addresses. The original call now
    # enters a trampoline; pi32v2 call sets rets without pushing onto the stack.
    source = source.replace(anchor, '\tcall lunar_stack_watermark_begin\n')
    return source + '''
\t.section .text.lunar_stack_watermark,"ax",@progbits
\t.globl lunar_stack_watermark_begin
lunar_stack_watermark_begin:
\tr1 = _ustack_lo
\tr2 = _ustack_top
\tr3 = 0xA55AA55A
lunar_stack_watermark_user:
\t[r1] = r3
\tr1 += 4
\tif (r1 != r2) goto lunar_stack_watermark_user
\tr1 = _sstack_lo
\tr2 = _sstack_top
lunar_stack_watermark_system:
\t[r1] = r3
\tr1 += 4
\tif (r1 != r2) goto lunar_stack_watermark_system
\t.globl lunar_stack_watermark_end
lunar_stack_watermark_end:
\tcall fm1_cstart
\tgoto .
'''
