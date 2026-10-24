#!/usr/bin/env python3
"""Private dev-kit UART control. No loader, flash, eFuse or USB commands.

Stop the receive-only UART capture first; this process must own the Tigard
UART exclusively. Requires the opt-in control firmware and Tigard TX -> PA5.
Default operation is a harmless PING. ROM entry requires --enter-uboot.
"""
import argparse
import time

TIGARD_PORT = '/dev/serial/by-id/usb-SecuringHardware.com_Tigard_V1.1_TG1108fc-if00-port0'


def exchange(uart, enter=False, timeout=3.0):
    """Require a live diagnostic acknowledgment before each transition step."""
    def command(text, expected):
        uart.write(text.encode('ascii') + b'\n')
        uart.flush()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            # Serial timeout is bounded by the caller; ignore unrelated logs.
            line = uart.read_until(b'\n', 512)
            if expected in line:
                return
        raise RuntimeError('No diagnostic acknowledgment: ' + expected.decode('ascii'))

    command('LUNAR PING', b'LUNAR_CONTROL pong=1')
    if enter:
        command('LUNAR ARM UBOOT', b'LUNAR_CONTROL armed=1')
        command('LUNAR ENTER UBOOT', b'LUNAR_CONTROL entering=uboot')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--enter-uboot', action='store_true')
    args = ap.parse_args()
    import serial
    # Set modem-control states before open, matching the receive-only capture.
    # DTR/RTS are not wired to Reset/Update and are never used for entry.
    uart = serial.Serial(port=None, baudrate=1000000, timeout=0.1,
                         write_timeout=1, exclusive=True, rtscts=False, dsrdtr=False)
    uart.dtr = False
    uart.rts = False
    uart.port = TIGARD_PORT
    try:
        uart.open()
        uart.reset_input_buffer()
        exchange(uart, args.enter_uboot)
    finally:
        uart.close()
    print('ROM entry acknowledged; verify USB enumeration separately.' if args.enter_uboot
          else 'Diagnostic PING acknowledged; no reset requested.')


if __name__ == '__main__':
    main()
