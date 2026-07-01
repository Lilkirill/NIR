from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseVendorAdapter(ABC):
    vendor_name: str

    @abstractmethod
    def parse(self, hostname: str, config_text: str) -> dict[str, Any]:
        raise NotImplementedError

    def normalize(self, parsed: dict[str, Any]) -> dict[str, Any]:
        return parsed

    def vendor_rules(self) -> list[dict[str, Any]]:
        return []

    def supported_profiles(self) -> list[str]:
        return ['default']

    def rule_overrides(
        self,
        *,
        validation_mode: str,
        source_scope: str,
        profile: str,
    ) -> dict[str, dict[str, Any]]:
        return {}

    def critical_test_names(self, *, validation_mode: str, profile: str) -> set[str]:
        return {
            'hostname_present',
            'at_least_one_interface',
            'addressed_interfaces_ratio',
            'route_consistency',
        }

    def assess_completeness(self, normalized: dict[str, Any]) -> dict[str, Any]:
        interfaces = normalized.get('interfaces', []) or []
        addressed = sum(1 for item in interfaces if item.get('addresses'))
        coverage = round(addressed / len(interfaces), 3) if interfaces else 0.0
        return {
            'status': 'complete' if coverage >= 0.5 else 'partial',
            'coverage': coverage,
            'notes': [],
        }
