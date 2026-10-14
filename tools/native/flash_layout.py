# SPDX-License-Identifier: MIT
"""Named native link budgets; these do not admit a package or hardware write."""

FLASH_LAYOUTS = ('protected', 'expanded-d7000', 'expanded-d9000')
RAW_APP_ORIGIN = 0x4120
EXPANDED_D7000_STAGE_START = 0xD7000
EXPANDED_D7000_STAGE_END = 0xD9000
EXPANDED_AREA_END = 0xD9000
# Reserve four-byte-aligned copies of the pinned FM-1_092 cfg-tool and cfg.
# The package verifier must independently check their real contents/extents.
EXPANDED_RECORD_RESERVE = 384 + 2940


def app_budget(profile='protected'):
    if profile == 'protected':
        return 0x8DFBC
    if profile == 'expanded-d7000':
        # Link below the proposed two-sector rescue stage and retain the same
        # independently checked cfg/tool metadata reserve as expanded-d9000.
        return EXPANDED_D7000_STAGE_START - RAW_APP_ORIGIN - EXPANDED_RECORD_RESERVE
    if profile == 'expanded-d9000':
        return EXPANDED_AREA_END - RAW_APP_ORIGIN - EXPANDED_RECORD_RESERVE
    raise ValueError('Unknown flash layout: ' + str(profile))


def linker_script(source, profile='protected'):
    """Adapt exactly the pinned XIP length, leaving entry and RAM map intact."""
    marker = 'ORIGIN = 0x02000120, LENGTH = 0x8DFBC'
    if source.count(marker) != 1:
        raise ValueError('Pinned XIP linker extent no longer matches')
    return source.replace(marker, 'ORIGIN = 0x02000120, LENGTH = 0x%X' % app_budget(profile))
