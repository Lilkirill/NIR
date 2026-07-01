from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class DeviceUpsertRequest(BaseModel):
    vendor: str = Field(..., description='cisco | juniper | mikrotik | arista | huawei')
    hostname: str
    ip_address: str | None = None
    site: str | None = None
    role: str | None = None
    environment: str | None = None
    collection_method: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationRequest(BaseModel):
    vendor: str = Field(..., description='cisco | juniper | mikrotik | arista | huawei')
    hostname: str
    config_text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    profile: str = 'default'
    redact_secrets: bool = False
    device_id: int | None = None
    device_ip: str | None = None
    management_ip: str | None = None
    site: str | None = None
    role: str | None = None
    environment: str | None = None
    run_kind: str | None = None
    source_scope: str | None = None
    expected_outcome: str | None = None
    include_ai: bool = False


class AIAnalysisRequest(ValidationRequest):
    include_ai: bool = True


class ValidationBulkRequest(BaseModel):
    items: list[ValidationRequest]


class CollectionRequest(BaseModel):
    source_type: Literal['file', 'ssh']
    vendor: str = Field(..., description='cisco | juniper | mikrotik | arista | huawei')
    hostname: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    file_path: str | None = None
    host: str | None = None
    port: int = 22
    username: str | None = None
    password: str | None = None
    command_override: str | None = None
    profile: str = 'default'
    redact_secrets: bool = False
    site: str | None = None
    role: str | None = None
    environment: str | None = None
    run_kind: str | None = None
    source_scope: str | None = None
    expected_outcome: str | None = None


class Finding(BaseModel):
    code: str
    severity: str
    message: str
    path: str | None = None
    category: str | None = None
    recommendation: str | None = None
    remediation_example: str | None = None
    rule_source: str | None = None
    rule_version: str | None = None
    confidence: float | None = None


class ValidationResponse(BaseModel):
    vendor: str
    hostname: str
    status: str
    normalized_config: dict[str, Any]
    errors: list[Finding]
    warnings: list[Finding]
    tests: list[dict[str, Any]]
    metrics: dict[str, Any]
    raw_config_path: str
    redacted_config_path: str | None = None
    raw_config_sha256: str | None = None
    raw_config_size: int | None = None
    config_snapshot_id: int | None = None
    normalized_config_id: int | None = None
    report_json_path: str
    report_html_path: str
    profile: str | None = None
    run_kind: str | None = None
    source_scope: str | None = None
    expected_outcome: str | None = None
    failure_kind: str | None = None
    profile_match_status: str | None = None
    profile_match_score: float | None = None
    dataset_name: str | None = None
    is_test_data: bool | None = None
    validation_mode: str | None = None
    critical_tests_failed: int | None = None
    issue_id: int | None = None
    ai_analysis: dict[str, Any] | None = None


class BulkValidationResponse(BaseModel):
    total: int
    passed: int
    failed: int
    results: list[ValidationResponse]


class CollectionResponse(BaseModel):
    snapshot_id: int
    vendor: str
    hostname: str
    source_type: str
    source_ref: str
    source_scope: str | None = None
    dataset_name: str | None = None
    is_test_data: bool | None = None
    metadata: dict[str, Any]
    raw_config_path: str
    redacted_config_path: str | None = None
    raw_config_sha256: str
    raw_config_size: int
    profile: str | None = None


class DeviceSummary(BaseModel):
    id: int
    vendor: str
    hostname: str
    hostname_normalized: str | None = None
    identity_key: str | None = None
    aliases: list[str] = Field(default_factory=list)
    ip_address: str | None = None
    site: str | None = None
    role: str | None = None
    environment: str | None = None
    collection_method: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    last_status: str | None = None
    last_seen_at: str


class ValidationRunSummary(BaseModel):
    id: int
    vendor: str
    hostname: str
    status: str
    profile: str | None = None
    source_type: str | None = None
    run_kind: str | None = None
    source_scope: str | None = None
    expected_outcome: str | None = None
    failure_kind: str | None = None
    profile_match_status: str | None = None
    dataset_name: str | None = None
    is_test_data: bool | None = None
    report_json_path: str
    report_html_path: str
    raw_config_path: str
    redacted_config_path: str | None = None
    created_at: str


class MetricsVendorSummary(BaseModel):
    vendor: str
    total_runs: int
    passed_runs: int
    failed_runs: int
    avg_execution_time_sec: float | None = None


class MetricsCodeSummary(BaseModel):
    code: str
    total: int


class MetricsFailureKindSummary(BaseModel):
    failure_kind: str
    total: int


class MetricsSummaryResponse(BaseModel):
    scope: str = 'all'
    total_runs: int
    passed_runs: int
    failed_runs: int
    unexpected_failed_runs: int = 0
    pass_rate: float
    avg_execution_time_sec: float
    avg_coverage_ratio: float
    latest_run_id: int | None = None
    open_issues: int = 0
    by_vendor: list[MetricsVendorSummary]
    by_code: list[MetricsCodeSummary]
    by_failure_kind: list[MetricsFailureKindSummary] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str


class TopologyValidationRequest(BaseModel):
    items: list[ValidationRequest]


class TopologyValidationResponse(BaseModel):
    findings: list[Finding]
    duplicate_ip_addresses: dict[str, list[str]] = Field(default_factory=dict)
    duplicate_hostnames: list[str] = Field(default_factory=list)


class DiffResponse(BaseModel):
    device_id: int
    hostname: str
    vendor: str
    from_snapshot_id: int
    to_snapshot_id: int
    changes: dict[str, Any]


class JobResponse(BaseModel):
    job_id: str
    status: str
    submitted_at: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    submitted_at: str
    finished_at: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class IssueSummary(BaseModel):
    id: int
    device_id: int | None = None
    latest_validation_run_id: int | None = None
    status: str
    severity: str
    root_cause: str | None = None
    summary: str
    assigned_to: str | None = None
    first_seen_at: str
    last_seen_at: str
    resolved_at: str | None = None
    occurrences_count: int


class IssueDetail(IssueSummary):
    issue_key: str
    details: str | None = None
    resolution_comment: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IssueUpdateRequest(BaseModel):
    status: str | None = None
    severity: str | None = None
    assigned_to: str | None = None
    resolution_comment: str | None = None


class RunArtifactsResponse(BaseModel):
    run_id: int
    vendor: str
    hostname: str
    status: str
    raw_config_path: str
    redacted_config_path: str | None = None
    report_json_path: str
    report_html_path: str
    config_snapshot_id: int | None = None
    normalized_config_id: int | None = None
