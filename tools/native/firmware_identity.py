# SPDX-License-Identifier: MIT
"""Explicit application identity for private native builds, not OTA admission."""
import re


def identity_configuration(identity=None):
    """Keep historical probes stable; reserve explicit builds for Lunar 5xx."""
    if identity is not None and (
            not isinstance(identity, str) or
            re.fullmatch(r"FM-1_5[0-9]{2}", identity) is None):
        raise ValueError("native Lunar identity must be FM-1_500 through FM-1_599")
    return dict(application_identity=identity or "FM-1_990",
                explicit=identity is not None,
                recovery_identity="FM-1_000",
                package_identity_verified=False,
                updater_acceptance_verified=False,
                hardware_identity_verified=False)


def platform_with_identity(source, identity=None):
    """Override the pinned HAL's guarded macro without modifying vendor files."""
    receipt = identity_configuration(identity)
    guard = '#ifndef LUNAR_ID\n#define LUNAR_ID "FM-1_990"'
    if source.count(guard) != 1:
        raise ValueError("pinned native application identity guard changed")
    if identity is None:
        return source
    return '#define LUNAR_ID "' + receipt["application_identity"] + '"\n' + source
