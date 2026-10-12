"""MIT. Pure replay of the distinct preparation-stop reader's actual receipt.

No files, device openers, source activation, or recovery authority. The caller
must freeze source/provenance, marker, plan, publications and owned wire capture
separately. Ambiguous receipts preserve partial replies without proving boot.
"""
import hashlib
import json
import math

from fm1_sdk_trace_read_wire import OPERATIONS, canonical, verify_native_receipt

NAMES = ('inquiry', 'trace-a', 'stage-a', 'trace-b', 'stage-b')
STATUS = ('status', 'masked', 'msg', 'host', 'driver', 'resid', 'info', 'sense_len')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def verify_receipt(outer_raw, native_raw, seal, raw_files, mapping, *, interpret,
                   evaluated_at, result_raw=None, pending_raw=None):
    """Validate exact logged requests, retained replies and publication outcome.

    A consumed attempt killed before its terminal record needs a different
    capture-backed admission. This kernel deliberately refuses that shape.
    Successful replay alone never authorizes following loader commands.
    """
    if (type(outer_raw) is not bytes or len(outer_raw) > 65536 or
            type(seal) is not bytes or len(seal) > 65536 or
            type(raw_files) is not dict or set(raw_files) - set(NAMES) or
            type(evaluated_at) not in (int, float) or not math.isfinite(evaluated_at)):
        raise ValueError('Bounded original receipt bytes required')
    rows = [json.loads(line) for line in outer_raw.splitlines()]
    if not rows or len(rows) > 13 or any(type(row) is not dict for row in rows):
        raise ValueError('Bounded terminal receipt required')
    times = [row.get('time') for row in rows]
    if (any(type(t) not in (int, float) or not math.isfinite(t) or t < 0 for t in times)
            or times != sorted(times) or times[-1] > evaluated_at):
        raise ValueError('Finite original receipt chronology required')
    position = 0

    def event(expected):
        nonlocal position
        if (position >= len(rows) or
                canonical({k: v for k, v in rows[position].items() if k != 'time'}) != canonical(expected)):
            raise ValueError('Exact distinct reader event required')
        position += 1

    event(dict(event='read_prepared', campaign_sha256=digest(seal), commands=5,
               upload_operations=0, reset_operations=0, flash_operations=0))
    completions, good, intents = [], [], 0
    for index, (cdb, count) in enumerate(OPERATIONS):
        if position == len(rows) or rows[position].get('event') != 'submit_intent':
            break
        event(dict(event='submit_intent', index=index, cdb=cdb.hex(), in_len=count,
                   out_len=0, retry=False))
        intents += 1
        if position == len(rows) or rows[position].get('event') != 'completion':
            break
        row = rows[position]
        keys = {'time', 'event', 'index', *STATUS, 'response_sha256',
                'actual_response_bytes', 'sense_hex', 'retry'}
        if (set(row) != keys or type(row['index']) is not int or row['index'] != index
                or row['retry'] is not False or any(type(row[k]) is not int for k in STATUS)
                or type(row['actual_response_bytes']) is not int
                or not 0 <= row['actual_response_bytes'] <= count
                or type(row['response_sha256']) is not str
                or len(row['response_sha256']) != 64
                or any(c not in '0123456789abcdef' for c in row['response_sha256'])
                or type(row['sense_hex']) is not str or len(row['sense_hex']) > 64
                or len(row['sense_hex']) % 2
                or any(c not in '0123456789abcdef' for c in row['sense_hex'])):
            raise ValueError('Exact actual native completion required')
        position += 1
        completions.append(row)
        good.append(all(row[k] == 0 for k in STATUS) and
                    row['actual_response_bytes'] == count and row['sense_hex'] == '')
        if not good[-1]:
            break
    # Publication happens after each completion, before the next request.
    for index, name in enumerate(NAMES):
        if name in raw_files:
            data = raw_files[name]
            if (index >= len(completions) or type(data) is not bytes
                    or len(data) != completions[index]['actual_response_bytes']
                    or digest(data) != completions[index]['response_sha256']):
                raise ValueError('Retained reply differs from actual completion')
        elif index < intents - 1:
            raise ValueError('Earlier reply publication missing before next completion')
    if intents > 1 and (raw_files['inquiry'][8:16].strip() != b'WL82' or
                        raw_files['inquiry'][16:32].strip() != b'UBOOT1.00'):
        raise ValueError('Later request after invalid ROM inquiry')
    expected = None
    if position < len(rows) and rows[position].get('event') == 'coherent_capture_completed':
        if len(good) != 5 or not all(good) or set(raw_files) != set(NAMES):
            raise ValueError('Five complete actual reply publications required')
        inquiry = raw_files['inquiry']
        if inquiry[8:16].strip() != b'WL82' or inquiry[16:32].strip() != b'UBOOT1.00':
            raise ValueError('Original ROM inquiry required')
        expected = dict(interpret(*(raw_files[n] for n in NAMES[1:])),
            campaign_sha256=digest(seal), preparation_outcome='failed-before-original-native-worker',
            raw_sha256=[digest(raw_files[n]) for n in NAMES])
        event(dict(event='coherent_capture_completed', **expected, retry=False))
    if position < len(rows):
        row = rows[position]
        if (set(row) != {'time', 'event', 'error', 'retry', 'classification'} or
                row['event'] != 'capture_stopped_ambiguous' or row['retry'] is not False
                or row['classification'] != 'inconclusive' or type(row['error']) is not str
                or not 0 < len(row['error']) <= 128):
            raise ValueError('Exact terminal ambiguity required')
        position += 1
        outcome = 'stopped-ambiguous'
        if result_raw is not None or (pending_raw is not None and
                (expected is None or pending_raw != canonical(expected))):
            raise ValueError('Ambiguous stop cannot publish success')
    else:
        outcome = 'completed'
        if expected is None or result_raw != canonical(expected) or pending_raw is not None:
            raise ValueError('Exact completed publication required')
    if position != len(rows):
        raise ValueError('Later transcript rows prohibited')
    native = verify_native_receipt(native_raw, outer_raw, mapping, outcome=outcome)
    return dict(outcome=outcome, started_at=times[0], terminal_at=times[-1],
                retained_replies=len(raw_files), native=native, result=expected,
                recovery_authorized=False, physical_boot_verified=False)
