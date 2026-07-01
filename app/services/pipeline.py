from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.models import ConfigSnapshot, Device, MetricsSnapshot, NormalizedConfig, ValidationFinding, ValidationRun
from app.core.vendor_registry import get_vendor_adapter
from app.reports.report_builder import ReportBuilder
from app.services.collection import _get_or_create_device
from app.services.context import infer_run_context
from app.services.failure_classifier import classify_failure
from app.services.issues import IssueService
from app.services.ai_model import ConfigGuardQwenAdvisor
from app.services.metrics import Timer
from app.services.profile_match import evaluate_profile_match
from app.services.redaction import redact_config_text
from app.services.storage import save_config_bundle
from app.validators.rule_engine import RuleEngine
from app.validators.schema_validator import SchemaValidator
from app.validators.test_engine import TestEngine

logger = get_logger()


@dataclass(slots=True)
class PersistedArtifacts:
    snapshot_id: int
    normalized_config_id: int
    raw_config_path: str
    redacted_config_path: str | None
    raw_config_sha256: str
    raw_config_size: int
    device_id: int | None


class ValidationPipeline:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.schema_validator = SchemaValidator()
        self.test_engine = TestEngine()
        self.report_builder = ReportBuilder()
        self.issue_service = IssueService(db)
        self.ai_advisor = ConfigGuardQwenAdvisor()

    def run(
        self,
        vendor: str,
        hostname: str,
        config_text: str,
        metadata: dict | None = None,
        source_type: str = 'api',
        source_ref: str = 'api://validate',
        profile: str = 'default',
        redact_secrets: bool = False,
        device_id: int | None = None,
        device_ip: str | None = None,
        management_ip: str | None = None,
        site: str | None = None,
        role: str | None = None,
        environment: str | None = None,
        run_kind: str | None = None,
        source_scope: str | None = None,
        expected_outcome: str | None = None,
        include_ai: bool = False,
    ) -> dict:
        metadata = metadata or {}
        adapter = get_vendor_adapter(vendor)
        run_context = infer_run_context(
            metadata=metadata,
            source_type=source_type,
            run_kind=run_kind,
            source_scope=source_scope,
            expected_outcome=expected_outcome,
            environment=environment,
        )
        profile_match = evaluate_profile_match(vendor=vendor, profile=profile)
        validation_mode = self._resolve_validation_mode(run_context)
        rule_engine = RuleEngine(vendor=vendor, profile=profile, validation_mode=validation_mode, source_scope=run_context['source_scope'])

        with Timer() as timer:
            normalized = adapter.normalize(adapter.parse(hostname=hostname, config_text=config_text))
            findings = self.schema_validator.validate(normalized) + rule_engine.evaluate(normalized)
            tests = self.test_engine.run(normalized)

        errors = [self._enrich_finding(item) for item in findings if item['severity'] == 'error']
        warnings = [self._enrich_finding(item) for item in findings if item['severity'] != 'error']
        failed_tests = [item for item in tests if item['status'] == 'failed']
        critical_tests = adapter.critical_test_names(validation_mode=validation_mode, profile=profile)
        critical_failed_tests = [item for item in failed_tests if item['name'] in critical_tests]
        status = 'passed' if not errors and not critical_failed_tests else 'failed'
        payload_hostname = normalized.get('hostname', hostname)
        failure_kind = classify_failure(errors=errors, failed_tests=critical_failed_tests, profile_match_status=str(profile_match['status']))

        metrics = {
            'execution_time_sec': round(timer.elapsed, 6),
            'interfaces_total': len(normalized.get('interfaces', [])),
            'routes_total': len(normalized.get('routes', [])),
            'errors_total': len(errors),
            'warnings_total': len(warnings),
            'tests_total': len(tests),
            'tests_failed': len(failed_tests),
            'coverage_ratio': round(len(tests) / 4, 3),
            'metadata': metadata,
            'profile': profile,
            'run_kind': run_context['run_kind'],
            'source_scope': run_context['source_scope'],
            'expected_outcome': run_context['expected_outcome'],
            'failure_kind': failure_kind,
            'profile_match_status': profile_match['status'],
            'profile_match_score': profile_match['score'],
            'dataset_name': run_context['dataset_name'],
            'is_test_data': run_context['is_test_data'],
            'validation_mode': validation_mode,
            'critical_tests_failed': len(critical_failed_tests),
        }

        persisted = self._persist_configuration(
            vendor=vendor,
            hostname=payload_hostname,
            config_text=config_text,
            normalized=normalized,
            source_type=source_type,
            source_ref=source_ref,
            profile=profile,
            redact_secrets=redact_secrets,
            explicit_device_id=device_id,
            device_ip=management_ip or device_ip,
            site=site,
            role=role,
            environment=environment,
            metadata=metadata,
            source_scope=run_context['source_scope'],
            dataset_name=run_context['dataset_name'],
            is_test_data=run_context['is_test_data'],
        )

        recommendations = self._build_recommendations(errors, warnings)
        ai_analysis = None
        if include_ai:
            ai_analysis = self.ai_advisor.analyze(
                vendor=vendor,
                hostname=payload_hostname,
                config_text=config_text,
                normalized_config=normalized,
                findings=errors + warnings,
                validation_status=status,
            )
        payload = {
            'vendor': vendor,
            'hostname': payload_hostname,
            'status': status,
            'normalized_config': normalized,
            'errors': errors,
            'warnings': warnings,
            'tests': tests,
            'metrics': metrics,
            'profile': profile,
            'run_kind': run_context['run_kind'],
            'source_scope': run_context['source_scope'],
            'expected_outcome': run_context['expected_outcome'],
            'failure_kind': failure_kind,
            'profile_match_status': profile_match['status'],
            'profile_match_score': profile_match['score'],
            'dataset_name': run_context['dataset_name'],
            'is_test_data': run_context['is_test_data'],
            'validation_mode': validation_mode,
            'critical_tests_failed': len(critical_failed_tests),
            'raw_config_path': persisted.raw_config_path,
            'redacted_config_path': persisted.redacted_config_path,
            'raw_config_sha256': persisted.raw_config_sha256,
            'raw_config_size': persisted.raw_config_size,
            'config_snapshot_id': persisted.snapshot_id,
            'normalized_config_id': persisted.normalized_config_id,
            'recommendations': recommendations,
            'ai_analysis': ai_analysis,
        }
        json_path, html_path = self.report_builder.build(payload)
        payload['report_json_path'] = json_path
        payload['report_html_path'] = html_path

        run = ValidationRun(
            device_id=persisted.device_id,
            vendor=vendor,
            hostname=payload_hostname,
            status=status,
            profile=profile,
            source_type=source_type,
            run_kind=run_context['run_kind'],
            source_scope=run_context['source_scope'],
            expected_outcome=run_context['expected_outcome'],
            failure_kind=failure_kind,
            profile_match_status=str(profile_match['status']),
            profile_match_score=float(profile_match['score']),
            dataset_name=run_context['dataset_name'],
            is_test_data=bool(run_context['is_test_data']),
            errors_json=json.dumps(errors, ensure_ascii=False),
            warnings_json=json.dumps(warnings, ensure_ascii=False),
            metrics_json=json.dumps(metrics, ensure_ascii=False),
            metadata_json=json.dumps(metadata, ensure_ascii=False),
            report_json_path=json_path,
            report_html_path=html_path,
            raw_config_path=persisted.raw_config_path,
            redacted_config_path=persisted.redacted_config_path,
            config_snapshot_id=persisted.snapshot_id,
            normalized_config_id=persisted.normalized_config_id,
        )
        self.db.add(run)
        self.db.flush()

        for finding in errors + warnings:
            self.db.add(
                ValidationFinding(
                    validation_run_id=run.id,
                    code=finding['code'],
                    severity=finding['severity'],
                    category=finding.get('category'),
                    message=finding['message'],
                    path=finding.get('path'),
                    recommendation=finding.get('recommendation'),
                    remediation_example=finding.get('remediation_example'),
                    rule_source=finding.get('rule_source'),
                    rule_version=finding.get('rule_version'),
                    confidence=finding.get('confidence'),
                )
            )

        self.db.add(
            MetricsSnapshot(
                validation_run_id=run.id,
                vendor=vendor,
                hostname=payload_hostname,
                status=status,
                run_kind=run_context['run_kind'],
                source_scope=run_context['source_scope'],
                failure_kind=failure_kind,
                execution_time_sec=metrics['execution_time_sec'],
                interfaces_total=metrics['interfaces_total'],
                routes_total=metrics['routes_total'],
                errors_total=metrics['errors_total'],
                warnings_total=metrics['warnings_total'],
                tests_total=metrics['tests_total'],
                tests_failed=metrics['tests_failed'],
                coverage_ratio=metrics['coverage_ratio'],
            )
        )

        device = self.db.query(Device).filter(Device.id == persisted.device_id).one_or_none() if persisted.device_id else None
        if device:
            device.last_status = status

        issue_id = self.issue_service.sync_for_run(run=run, findings=errors + warnings)
        self.db.commit()
        payload['issue_id'] = issue_id
        logger.info(
            'validation vendor=%s hostname=%s status=%s run_kind=%s scope=%s expected=%s failure_kind=%s errors=%s warnings=%s tests_failed=%s raw_config_path=%s report_json=%s',
            vendor,
            payload_hostname,
            status,
            run_context['run_kind'],
            run_context['source_scope'],
            run_context['expected_outcome'],
            failure_kind,
            len(errors),
            len(warnings),
            len(critical_failed_tests),
            persisted.raw_config_path,
            json_path,
        )
        return payload

    @staticmethod
    def _resolve_validation_mode(run_context: dict[str, Any]) -> str:
        if run_context.get('run_kind') in {'dataset', 'regression'} or run_context.get('is_test_data'):
            return 'dataset'
        if run_context.get('source_scope') == 'production':
            return 'strict'
        return 'standard'

    def _persist_configuration(
        self,
        vendor: str,
        hostname: str,
        config_text: str,
        normalized: dict,
        source_type: str,
        source_ref: str,
        profile: str,
        redact_secrets: bool,
        explicit_device_id: int | None,
        device_ip: str | None,
        site: str | None,
        role: str | None,
        environment: str | None,
        metadata: dict[str, Any],
        source_scope: str,
        dataset_name: str | None,
        is_test_data: bool,
    ) -> PersistedArtifacts:
        redacted_text = redact_config_text(config_text) if redact_secrets else None
        saved = save_config_bundle(vendor=vendor, hostname=hostname, config_text=config_text, redacted_text=redacted_text)
        device = _get_or_create_device(
            self.db,
            vendor=vendor,
            hostname=hostname,
            ip_address=device_ip,
            site=site,
            role=role,
            environment=environment,
            collection_method=source_type,
            metadata=metadata,
            explicit_device_id=explicit_device_id,
        )

        snapshot = ConfigSnapshot(
            device_id=device.id,
            vendor=vendor,
            hostname=hostname,
            source_type=source_type,
            source_ref=source_ref,
            source_scope=source_scope,
            dataset_name=dataset_name,
            is_test_data=is_test_data,
            raw_config_path=saved.raw.path,
            redacted_config_path=saved.redacted.path if saved.redacted else None,
            raw_config_sha256=saved.raw.sha256,
            raw_config_size=saved.raw.size_bytes,
            collected_success='true',
            profile=profile,
            metadata_json=json.dumps(metadata, ensure_ascii=False),
        )
        self.db.add(snapshot)
        self.db.flush()

        normalized_json = json.dumps(normalized, ensure_ascii=False)
        normalized_row = NormalizedConfig(
            config_snapshot_id=snapshot.id,
            vendor=vendor,
            hostname=hostname,
            schema_version='1.0',
            normalized_json=normalized_json,
            vendor_extensions_json=json.dumps({'vendor': vendor}, ensure_ascii=False),
            normalized_hash=hashlib.sha256(normalized_json.encode('utf-8')).hexdigest(),
            parsed_successfully=True,
        )
        self.db.add(normalized_row)
        self.db.flush()
        return PersistedArtifacts(
            snapshot_id=snapshot.id,
            normalized_config_id=normalized_row.id,
            raw_config_path=saved.raw.path,
            redacted_config_path=saved.redacted.path if saved.redacted else None,
            raw_config_sha256=saved.raw.sha256,
            raw_config_size=saved.raw.size_bytes,
            device_id=device.id,
        )

    @staticmethod
    def _build_recommendations(errors: list[dict], warnings: list[dict]) -> list[str]:
        recs = [item['recommendation'] for item in errors + warnings if item.get('recommendation')]
        return list(dict.fromkeys(recs))

    @staticmethod
    def _enrich_finding(finding: dict[str, Any]) -> dict[str, Any]:
        mapping = {
            'SSH_REQUIRED': {
                'recommendation': 'Enable SSH management access for secure administration.',
                'remediation_example': 'line vty 0 4\n transport input ssh',
                'rule_source': 'generic',
            },
            'DEFAULT_ROUTE_REQUIRED': {
                'recommendation': 'Configure a default route or an equivalent upstream gateway.',
                'remediation_example': 'ip route 0.0.0.0 0.0.0.0 <next-hop>',
                'rule_source': 'generic',
            },
            'PASSWORD_ENCRYPTION_REQUIRED': {
                'recommendation': 'Enable password encryption for locally stored secrets.',
                'remediation_example': 'service password-encryption',
                'rule_source': 'generic',
            },
            'ADMIN_USER_REQUIRED': {
                'recommendation': 'Create an administrative account with privileged access.',
                'remediation_example': 'username admin privilege 15 secret 5 <secret>',
                'rule_source': 'generic',
            },
            'BRANCH_HOSTNAME_PREFIX': {
                'recommendation': 'Rename the device to match the selected profile naming convention.',
                'remediation_example': 'hostname BRANCH-<site>-<role>-<id>',
                'rule_source': 'profile',
            },
            'DUPLICATE_IP_ADDRESS': {
                'recommendation': 'Assign unique interface addressing across connected devices.',
                'remediation_example': 'Update one of the conflicting interface addresses.',
                'rule_source': 'topology',
            },
        }
        enriched = dict(finding)
        for key, value in mapping.get(finding.get('code'), {}).items():
            enriched.setdefault(key, value)
        enriched.setdefault('rule_version', '1.0')
        enriched.setdefault('confidence', 1.0)
        return enriched
