from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base



def utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Device(Base):
    __tablename__ = 'devices'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor: Mapped[str] = mapped_column(String(32), nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    hostname_normalized: Mapped[str] = mapped_column(String(255), nullable=False, default='')
    identity_key: Mapped[str] = mapped_column(String(255), nullable=False, default='')
    aliases_json: Mapped[str] = mapped_column(Text, default='[]', nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    site: Mapped[str | None] = mapped_column(String(128), nullable=True)
    role: Mapped[str | None] = mapped_column(String(128), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(64), nullable=True)
    collection_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default='{}', nullable=False)
    last_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ConfigSnapshot(Base):
    __tablename__ = 'config_snapshots'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('devices.id'), nullable=True)
    vendor: Mapped[str] = mapped_column(String(32), nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(1024), default='', nullable=False)
    source_scope: Mapped[str] = mapped_column(String(64), default='unknown', nullable=False)
    dataset_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_test_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_config_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    redacted_config_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    raw_config_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_config_size: Mapped[int] = mapped_column(Integer, nullable=False)
    collected_success: Mapped[str] = mapped_column(String(16), default='true', nullable=False)
    profile: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default='{}', nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)


class NormalizedConfig(Base):
    __tablename__ = 'normalized_configs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_snapshot_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('config_snapshots.id'), nullable=True)
    vendor: Mapped[str] = mapped_column(String(32), nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), default='1.0', nullable=False)
    normalized_json: Mapped[str] = mapped_column(Text, nullable=False)
    vendor_extensions_json: Mapped[str] = mapped_column(Text, default='{}', nullable=False)
    normalized_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parsed_successfully: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)


class ValidationRun(Base):
    __tablename__ = 'validation_runs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('devices.id'), nullable=True)
    vendor: Mapped[str] = mapped_column(String(32), nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    profile: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    run_kind: Mapped[str] = mapped_column(String(32), default='api', nullable=False)
    source_scope: Mapped[str] = mapped_column(String(64), default='unknown', nullable=False)
    expected_outcome: Mapped[str] = mapped_column(String(32), default='unknown', nullable=False)
    failure_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    profile_match_status: Mapped[str] = mapped_column(String(32), default='matched', nullable=False)
    profile_match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    dataset_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_test_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    errors_json: Mapped[str] = mapped_column(Text, default='[]')
    warnings_json: Mapped[str] = mapped_column(Text, default='[]')
    metrics_json: Mapped[str] = mapped_column(Text, default='{}', nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, default='{}', nullable=False)
    report_json_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    report_html_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    raw_config_path: Mapped[str] = mapped_column(String(1024), default='', nullable=False)
    redacted_config_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    config_snapshot_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    normalized_config_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)


class ValidationFinding(Base):
    __tablename__ = 'validation_findings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    validation_run_id: Mapped[int] = mapped_column(Integer, ForeignKey('validation_runs.id'), nullable=False)
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    remediation_example: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rule_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)


class ConfigIssue(Base):
    __tablename__ = 'config_issues'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('devices.id'), nullable=True)
    latest_validation_run_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('validation_runs.id'), nullable=True)
    issue_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), default='open', nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default='medium', nullable=False)
    root_cause: Mapped[str | None] = mapped_column(String(64), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolution_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurrences_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, default='{}', nullable=False)


class IssueOccurrence(Base):
    __tablename__ = 'issue_occurrences'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(Integer, ForeignKey('config_issues.id'), nullable=False)
    validation_run_id: Mapped[int] = mapped_column(Integer, ForeignKey('validation_runs.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)


class MetricsSnapshot(Base):
    __tablename__ = 'metrics_snapshots'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    validation_run_id: Mapped[int] = mapped_column(Integer, ForeignKey('validation_runs.id'), nullable=False)
    vendor: Mapped[str] = mapped_column(String(32), nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    run_kind: Mapped[str] = mapped_column(String(32), default='api', nullable=False)
    source_scope: Mapped[str] = mapped_column(String(64), default='unknown', nullable=False)
    failure_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    execution_time_sec: Mapped[float] = mapped_column(Float, nullable=False)
    interfaces_total: Mapped[int] = mapped_column(Integer, nullable=False)
    routes_total: Mapped[int] = mapped_column(Integer, nullable=False)
    errors_total: Mapped[int] = mapped_column(Integer, nullable=False)
    warnings_total: Mapped[int] = mapped_column(Integer, nullable=False)
    tests_total: Mapped[int] = mapped_column(Integer, nullable=False)
    tests_failed: Mapped[int] = mapped_column(Integer, nullable=False)
    coverage_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)
