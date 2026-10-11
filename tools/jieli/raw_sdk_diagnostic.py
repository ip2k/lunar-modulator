#!/usr/bin/env python3
"""MIT. Offline SDK diagnostic gate for the recorded FM-1_092 NOR layout.

Separate from the SDK-free diagnostic policy. No USB or physical write permit.
"""
import audit_sdk_diagnostic as native
import raw_flash_profile as raw
from audit_link import Elf, audit


def profile_dump(baseline_a, baseline_b, manifest, identity, reference, baseline_profile):
    if baseline_profile == 'recorded-original-loader':
        return raw.profile_dump(baseline_a, baseline_b, manifest, identity, reference)
    if baseline_profile == 'fixed-loader':
        return raw.profile_dump_fixed_loader(baseline_a, baseline_b, manifest, identity, reference)
    raise ValueError('Explicit supported backup provenance required')


def validate_target(baseline_a, baseline_b, target, manifest, identity, reference,
                    app, elf, baseline_profile='recorded-original-loader', expected_native_audit=None):
    profile = profile_dump(baseline_a, baseline_b, manifest, identity, reference, baseline_profile)
    if not isinstance(app, bytes) or not 0 < len(app) <= raw.APP_BYTES:
        raise ValueError('Nonempty immutable SDK image must fit recorded application extent')
    # Recompute both policies from actual bytes. A caller's passed JSON is
    # never evidence. The key auditor's native-scheduling pending item remains
    # visible; the separate instruction gate checks its exact implementation.
    link = audit([('lunar-sdk-diagnostic.elf', Elf(elf))],
                 [('lunar-sdk-diagnostic.app.bin', app)], True, runtime='sdk')
    if link['passed'] is not True or link['n_fail'] != 0:
        raise ValueError('SDK key/eFuse link audit failed')
    layout = native.audit(elf, app)
    if layout.get('passed') is not True or layout.get('flashable') is not False:
        raise ValueError('SDK native diagnostic audit failed')
    if expected_native_audit is not None and raw.encoded(expected_native_audit) != raw.encoded(layout):
        raise ValueError('Supplied native audit differs from independently recomputed audit')
    result = raw._validate_target_geometry(profile, baseline_a, target, reference, app)
    result.update(diagnostic_profile='sdk-dual-core-private', baseline_profile=baseline_profile,
                  app_sha256=raw.digest(app), elf_sha256=raw.digest(elf),
                  link_audit=link, link_audit_sha256=raw.digest(raw.encoded(link)),
                  diagnostic_layout=layout, diagnostic_layout_sha256=raw.digest(raw.encoded(layout)),
                  status='exact-raw-sdk-app-target-verified-offline',
                  native_scheduling_checked=True,
                  irq_audit_limit='legacy link scan uses 0x01c801ec; native request_irq uses 0x01c7ffec',
                  next_gate='Independent candidate/adapter/recovery review, then physical boot/display/restore')
    return result
