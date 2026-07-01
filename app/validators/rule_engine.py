from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.core.vendor_registry import get_vendor_adapter

BASE_DIR = Path(__file__).resolve().parents[2]
RULES_DIR = BASE_DIR / 'rules'


class RuleEngine:
    def __init__(
        self,
        vendor: str | None = None,
        profile: str = 'default',
        validation_mode: str = 'standard',
        source_scope: str = 'unknown',
    ) -> None:
        self.vendor = (vendor or '').lower()
        self.profile = profile or 'default'
        self.validation_mode = validation_mode or 'standard'
        self.source_scope = source_scope or 'unknown'
        self._rules_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}

    def _load_rules(self, vendor: str) -> list[dict[str, Any]]:
        cache_key = (vendor, self.profile)
        if cache_key in self._rules_cache:
            return self._rules_cache[cache_key]
        rules: list[dict[str, Any]] = []
        rules.extend(self._load_from_path(RULES_DIR / 'base_rules.yaml', 'generic'))
        if vendor:
            rules.extend(self._load_from_path(RULES_DIR / 'vendors' / f'{vendor}.yaml', 'vendor'))
        if self.profile and self.profile != 'default':
            rules.extend(self._load_from_path(RULES_DIR / 'profiles' / f'{self.profile}.yaml', 'profile'))
        self._rules_cache[cache_key] = rules
        return rules

    @staticmethod
    def _load_from_path(path: Path, source: str) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        content = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        rules = content.get('rules', [])
        for rule in rules:
            rule.setdefault('rule_source', source)
            rule.setdefault('rule_version', '1.0')
        return rules

    def evaluate(self, config: dict) -> list[dict]:
        vendor = self.vendor or str(config.get('vendor', '')).lower()
        adapter = get_vendor_adapter(vendor) if vendor else None
        rules = self._load_rules(vendor)
        findings = []
        rule_overrides = adapter.rule_overrides(
            validation_mode=self.validation_mode,
            source_scope=self.source_scope,
            profile=self.profile,
        ) if adapter else {}

        completeness = adapter.assess_completeness(config) if adapter else {'status': 'complete', 'coverage': 1.0, 'notes': []}
        completeness_notes = completeness.get('notes', []) or []

        for note in completeness_notes:
            findings.append({
                'code': f'{vendor.upper()}_PARTIAL_PARSE' if vendor else 'PARTIAL_PARSE',
                'severity': 'warning',
                'message': note,
                'path': 'normalized_config',
                'category': 'incomplete',
                'rule_source': 'vendor',
                'rule_version': '1.0',
                'confidence': 0.6,
            })

        for rule in rules:
            if not self._is_rule_applicable(rule):
                continue
            effective_rule = dict(rule)
            effective_rule.update(rule_overrides.get(rule.get('code', ''), {}))
            severity = self._resolve_severity(effective_rule)
            if severity in {None, 'ignore', 'disabled'}:
                continue
            effective_rule['severity'] = severity
            finding = self._evaluate_rule(effective_rule, config)
            if finding:
                findings.append(finding)
        return findings

    def _is_rule_applicable(self, rule: dict[str, Any]) -> bool:
        only_modes = set(rule.get('only_in_modes', []) or [])
        if only_modes and self.validation_mode not in only_modes:
            return False
        skip_modes = set(rule.get('skip_in_modes', []) or [])
        if self.validation_mode in skip_modes:
            return False
        only_scopes = set(rule.get('only_in_source_scopes', []) or [])
        if only_scopes and self.source_scope not in only_scopes:
            return False
        skip_scopes = set(rule.get('skip_in_source_scopes', []) or [])
        if self.source_scope in skip_scopes:
            return False
        profiles = set(rule.get('profiles', []) or [])
        if profiles and self.profile not in profiles:
            return False
        exclude_profiles = set(rule.get('exclude_profiles', []) or [])
        if self.profile in exclude_profiles:
            return False
        return True

    def _resolve_severity(self, rule: dict[str, Any]) -> str | None:
        severity = rule.get('severity')
        severity_by_mode = rule.get('severity_by_mode', {}) or {}
        severity_by_scope = rule.get('severity_by_source_scope', {}) or {}
        if self.source_scope in severity_by_scope:
            severity = severity_by_scope[self.source_scope]
        if self.validation_mode in severity_by_mode:
            severity = severity_by_mode[self.validation_mode]
        return severity

    def _evaluate_rule(self, rule: dict[str, Any], config: dict[str, Any]) -> dict[str, Any] | None:
        t = rule['type']
        if t == 'require_service_enabled':
            service = rule['service']
            if not config.get('services', {}).get(service, False):
                return self._finding(rule, f'Service {service} must be enabled.')
        elif t == 'require_default_route':
            if not any(r.get('destination') == '0.0.0.0/0' for r in config.get('routes', [])):
                return self._finding(rule, 'Default route is missing.')
        elif t == 'require_admin_user':
            admin_name = str(rule.get('username', 'admin')).lower()
            users = config.get('users', []) or []
            if not any(str(u.get('username', '')).lower() == admin_name for u in users):
                return self._finding(rule, 'Admin account is missing.')
        elif t == 'interface_requires_address':
            findings = []
            for iface in config.get('interfaces', []):
                if iface.get('enabled') and not iface.get('addresses'):
                    findings.append(self._finding(rule, f"Interface {iface['name']} is enabled but has no IP address."))
            if findings:
                # Return first finding for compatibility with existing list-based engine
                return findings[0]
        elif t == 'minimum_interfaces':
            minimum = int(rule.get('minimum', 1))
            if len(config.get('interfaces', [])) < minimum:
                return self._finding(rule, f'At least {minimum} interfaces are required.')
        elif t == 'require_hostname_prefix':
            prefix = str(rule.get('prefix', ''))
            hostname = str(config.get('hostname', ''))
            if prefix and not hostname.startswith(prefix):
                return self._finding(rule, f'Hostname must start with {prefix}.')
        return None

    @staticmethod
    def _finding(rule: dict, message: str) -> dict:
        return {
            'code': rule['code'],
            'severity': rule['severity'],
            'message': message,
            'path': rule.get('path'),
            'category': rule.get('category'),
            'rule_source': rule.get('rule_source'),
            'rule_version': rule.get('rule_version'),
            'recommendation': rule.get('recommendation'),
            'remediation_example': rule.get('remediation_example'),
            'confidence': float(rule.get('confidence', 1.0)) if rule.get('confidence') is not None else None,
        }
