from __future__ import annotations

from app.parsers.mikrotik import MikroTikParser
from app.vendors.base.adapter import BaseVendorAdapter


class MikroTikAdapter(BaseVendorAdapter):
    vendor_name = 'mikrotik'

    def parse(self, hostname: str, config_text: str) -> dict:
        return MikroTikParser().parse(hostname=hostname, config_text=config_text)

    def supported_profiles(self) -> list[str]:
        return ['default', 'branch-router', 'edge-router', 'firewall']

    def rule_overrides(self, *, validation_mode: str, source_scope: str, profile: str) -> dict[str, dict]:
        overrides: dict[str, dict] = {}
        if validation_mode == 'dataset' or source_scope in {'dataset', 'raw', 'partial'}:
            overrides['MIKROTIK_SSH_RECOMMENDED'] = {'severity': 'warning'}
            overrides['MIKROTIK_DEFAULT_ROUTE_RECOMMENDED'] = {'severity': 'warning'}
            overrides['MIKROTIK_ADMIN_USER_RECOMMENDED'] = {'severity': 'warning'}
        return overrides

    def critical_test_names(self, *, validation_mode: str, profile: str) -> set[str]:
        if validation_mode == 'dataset':
            return {'hostname_present', 'at_least_one_interface'}
        return {'hostname_present', 'at_least_one_interface', 'route_consistency'}

    def assess_completeness(self, normalized: dict[str, any]) -> dict[str, any]:
        interfaces = normalized.get('interfaces', []) or []
        addressed = sum(1 for item in interfaces if item.get('addresses'))
        coverage = round(addressed / len(interfaces), 3) if interfaces else 0.0
        notes = []
        if interfaces and addressed == 0:
            notes.append('No addressed interfaces were parsed from MikroTik config; relaxed validation is recommended.')
        status = 'complete' if coverage >= 0.25 else 'partial'
        return {'status': status, 'coverage': coverage, 'notes': notes}
