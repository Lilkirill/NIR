from __future__ import annotations


def classify_failure(*, errors: list[dict], failed_tests: list[dict], profile_match_status: str) -> str | None:
    if not errors and not failed_tests:
        return None
    if profile_match_status == 'mismatch':
        return 'failed_profile_mismatch'
    categories = {item.get('category') for item in errors if item.get('category')}
    if 'topology' in categories:
        return 'failed_topology'
    if 'schema' in categories:
        return 'failed_schema'
    if 'incomplete' in categories:
        return 'failed_incomplete'
    return 'failed_policy'
