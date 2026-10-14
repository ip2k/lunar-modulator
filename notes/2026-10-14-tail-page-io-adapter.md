# Unbound reserved-tail IO adapter — 2026-10-14

[verified] `firmware/native/tail_page_io.h` implements packed reads, page-split
programming and logical-block erases over two explicit equally sized sector
lists. It contains no device addresses and is not bound to SAVE or native OTA.
Initialization rejects duplicate, misaligned and out-of-device sectors, unequal
slots, impossible capacity and overflow; failed initialization clears readiness.
Operations reject cross-slot and malformed ranges before backend calls.

[verified] The existing full-bound storage fault harness now exercises this
implementation, rather than its test-only mapper. An independent packed reader
still checks recovered bytes. The exact proposed 24-sector map is test data:
12 physical sectors per slot, final 256-byte pages reserved, 45,056 logical bytes
per slot, and 45,024 bytes after the journal header. Distinct 43,130-byte payloads
exercise both slot replacement directions. Partial mutations and lost final
acknowledgements preserve the active slot and select an exact old or new body.
Reserved pages, unused suffix and every byte outside the proposed sectors are
checked. Duplicate/overflow/capacity/physical-limit initialization cases also
reject without mutation. The focused test passes on this Mac with ASan/UBSan.

Logical 4 KiB erases may cover two physical sectors and adjacent logical erases
may erase the same physical sector twice. This is safe only in an erase-all-
inactive-slot-before-program transaction, as `lunar_project_begin` currently
uses. The adapter does not support interleaving block erases and writes. Backend
NOR readiness, RAM closure and hardware ownership are separate requirements.

[verified] This change performs no device operation, migration or admission.
The fault model starts with reserved pages already erased. Initial migration
from opaque stock state, its interrupted erase states and physical recovery
remain unresolved. Capacity arithmetic and host tests cannot enable SAVE.
