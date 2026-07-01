from __future__ import annotations

from app.core.vendor_registry import get_vendor_adapter


def evaluate_profile_match(vendor: str, profile: str) -> dict[str, float | str]:
    if not profile or profile == 'default':
        return {'status': 'matched', 'score': 1.0}
    adapter = get_vendor_adapter(vendor)
    supported = set(adapter.supported_profiles())
    if profile in supported:
        return {'status': 'matched', 'score': 1.0}
    if any(profile.split('-')[0] in item for item in supported):
        return {'status': 'weak_match', 'score': 0.5}
    return {'status': 'mismatch', 'score': 0.0}
