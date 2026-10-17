# SPDX-License-Identifier: MIT
"""Small shared contracts for named private native diagnostic profiles."""

HALL_O2_STAGE7_PROFILE = "hall-o2-stage7-v1"
HALL_O2_STAGE7_REQUIRED_BY_GROUP = {
    "engines": frozenset(("macro", "shapes", "sixop", "drums")),
    "effects": frozenset(("hall",)),
}


def missing_hall_o2_stage7_modules(request):
    """Return required module IDs missing from their required selection groups."""
    return {
        group: sorted(required - set(request.get(group, ())))
        for group, required in HALL_O2_STAGE7_REQUIRED_BY_GROUP.items()
    }


def validate_hall_o2_stage7_modules(request):
    """Reject a named-profile request unless its exact grouped prerequisites are selected."""
    missing = missing_hall_o2_stage7_modules(request)
    missing = {group: ids for group, ids in missing.items() if ids}
    if missing:
        details = "; ".join(
            f"{group}: {', '.join(ids)}" for group, ids in sorted(missing.items())
        )
        raise ValueError(
            f"Named diagnostic profile {HALL_O2_STAGE7_PROFILE} requires caller-selected "
            f"modules in their catalogue groups ({details})"
        )
