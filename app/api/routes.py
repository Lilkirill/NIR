from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, text
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.core.config import BASE_DIR, settings
from app.core.database import SessionLocal, get_db
from app.core.models import ConfigIssue, Device, ValidationRun
from app.core.schemas import (
    AIAnalysisRequest,
    BulkValidationResponse,
    CollectionRequest,
    CollectionResponse,
    DeviceSummary,
    DeviceUpsertRequest,
    DiffResponse,
    HealthResponse,
    IssueDetail,
    IssueSummary,
    IssueUpdateRequest,
    JobResponse,
    JobStatusResponse,
    MetricsSummaryResponse,
    RunArtifactsResponse,
    TopologyValidationRequest,
    TopologyValidationResponse,
    ValidationBulkRequest,
    ValidationRequest,
    ValidationResponse,
    ValidationRunSummary,
    Finding,
)
from app.services.collection import CollectionService
from app.core.identity import build_identity_key, normalize_hostname
from app.services.diff import DiffService
from app.services.export import ExportService
from app.services.issues import IssueService
from app.services.jobs import job_store
from app.services.metrics import build_summary, render_prometheus_metrics
from app.services.pipeline import ValidationPipeline
from app.services.topology import validate_topology

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / 'templates'))


@router.get('/health', response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status='ok')


@router.get('/health/live', response_model=HealthResponse)
def live() -> HealthResponse:
    return HealthResponse(status='ok')


@router.get('/health/ready', response_model=HealthResponse)
def ready(db: Session = Depends(get_db)) -> HealthResponse:
    try:
        db.execute(text('SELECT 1'))
        return HealthResponse(status='ok')
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=503, detail=f'Not ready: {exc}') from exc


@router.get('/metrics', response_class=PlainTextResponse)
def prometheus_metrics(db: Session = Depends(get_db)) -> PlainTextResponse:
    return PlainTextResponse(render_prometheus_metrics(db), media_type='text/plain; version=0.0.4')


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    context = {
        'request': request,
        'title': settings.app_dashboard_title,
        'metrics': build_summary(db, scope='operational'),
        'devices': _list_devices(db),
        'runs': _list_runs(db, limit=10),
        'issues': _list_issues(db, limit=10),
    }
    return templates.TemplateResponse('dashboard.html.j2', context)


@router.post('/validate', response_model=ValidationResponse)
def validate_config(payload: ValidationRequest, db: Session = Depends(get_db)) -> ValidationResponse:
    try:
        result = ValidationPipeline(db=db).run(**payload.model_dump())
        return ValidationResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f'Internal validation error: {exc}') from exc




@router.post('/ai/analyze', response_model=ValidationResponse)
def ai_analyze_config(payload: AIAnalysisRequest, db: Session = Depends(get_db)) -> ValidationResponse:
    try:
        data = payload.model_dump()
        data['include_ai'] = True
        result = ValidationPipeline(db=db).run(**data)
        return ValidationResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f'Internal AI analysis error: {exc}') from exc

@router.post('/validate/bulk', response_model=BulkValidationResponse)
def validate_bulk(payload: ValidationBulkRequest, db: Session = Depends(get_db)) -> BulkValidationResponse:
    results = []
    passed = 0
    failed = 0
    for item in payload.items:
        result = ValidationPipeline(db=db).run(**item.model_dump())
        results.append(ValidationResponse(**result))
        if result['status'] == 'passed':
            passed += 1
        else:
            failed += 1
    return BulkValidationResponse(total=len(results), passed=passed, failed=failed, results=results)


@router.post('/validate/topology', response_model=TopologyValidationResponse)
def validate_topology_endpoint(payload: TopologyValidationRequest) -> TopologyValidationResponse:
    from app.parsers import get_parser

    normalized_items = []
    for item in payload.items:
        parser = get_parser(item.vendor)
        normalized_items.append(parser.parse(hostname=item.hostname, config_text=item.config_text))
    topology = validate_topology(normalized_items)
    return TopologyValidationResponse(**topology)


@router.post('/jobs/validate-bulk', response_model=JobResponse)
def submit_validate_bulk(payload: ValidationBulkRequest, background_tasks: BackgroundTasks) -> JobResponse:
    def _runner() -> dict:
        local_db = SessionLocal()
        try:
            response = validate_bulk(payload, db=local_db)
            return response.model_dump()
        finally:
            local_db.close()
    record = job_store.submit(background_tasks, _runner)
    return JobResponse(job_id=record.job_id, status=record.status, submitted_at=record.submitted_at)


@router.get('/jobs/{job_id}', response_model=JobStatusResponse)
def get_job_status(job_id: str) -> JobStatusResponse:
    record = job_store.get(job_id)
    if not record:
        raise HTTPException(status_code=404, detail=f'Job {job_id} not found')
    return JobStatusResponse(**record.__dict__)


@router.post('/collect', response_model=CollectionResponse)
def collect_config(payload: CollectionRequest, db: Session = Depends(get_db)) -> CollectionResponse:
    try:
        result = CollectionService(db=db).collect(**payload.model_dump())
        return CollectionResponse(**{k: result.get(k) for k in CollectionResponse.model_fields.keys()})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f'Internal collection error: {exc}') from exc


@router.post('/collect-and-validate', response_model=ValidationResponse)
def collect_and_validate(payload: CollectionRequest, db: Session = Depends(get_db)) -> ValidationResponse:
    try:
        collected = CollectionService(db=db).collect(**payload.model_dump())
        result = ValidationPipeline(db=db).run(
            vendor=collected['vendor'],
            hostname=collected['hostname'],
            config_text=collected['config_text'],
            metadata=collected['metadata'],
            source_type=collected['source_type'],
            source_ref=collected['source_ref'],
            profile=payload.profile,
            redact_secrets=payload.redact_secrets,
            device_ip=payload.host,
            site=payload.site,
            role=payload.role,
            environment=payload.environment,
            run_kind=payload.run_kind,
            source_scope=payload.source_scope,
            expected_outcome=payload.expected_outcome,
        )
        return ValidationResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f'Internal collect-and-validate error: {exc}') from exc


@router.get('/metrics/summary', response_model=MetricsSummaryResponse)
def metrics_summary(scope: str = Query('all', pattern='^(all|operational|dataset|test)$'), db: Session = Depends(get_db)) -> MetricsSummaryResponse:
    return MetricsSummaryResponse(**build_summary(db, scope=scope))


@router.post('/devices', response_model=DeviceSummary)
def upsert_device(payload: DeviceUpsertRequest, db: Session = Depends(get_db)) -> DeviceSummary:
    hostname_normalized = normalize_hostname(payload.hostname)
    identity_key = build_identity_key(payload.vendor, payload.hostname, management_ip=payload.ip_address)
    row = db.query(Device).filter(Device.identity_key == identity_key).order_by(Device.id.asc()).first()
    if row is None and payload.ip_address:
        row = db.query(Device).filter(Device.vendor == payload.vendor, Device.ip_address == payload.ip_address).order_by(Device.id.asc()).first()
    if row is None:
        row = db.query(Device).filter(Device.vendor == payload.vendor, func.lower(Device.hostname_normalized) == hostname_normalized).order_by(Device.id.asc()).first()
    metadata_json = json.dumps(payload.metadata, ensure_ascii=False)
    if row:
        previous_hostname = row.hostname
        row.hostname = payload.hostname
        row.hostname_normalized = hostname_normalized
        row.ip_address = payload.ip_address
        row.site = payload.site
        row.role = payload.role
        row.environment = payload.environment
        row.collection_method = payload.collection_method
        row.metadata_json = metadata_json
        aliases = json.loads(row.aliases_json or '[]')
        if previous_hostname and previous_hostname != payload.hostname and previous_hostname not in aliases:
            aliases.append(previous_hostname)
        row.aliases_json = json.dumps(sorted(dict.fromkeys(aliases)), ensure_ascii=False)
    else:
        row = Device(
            vendor=payload.vendor,
            hostname=payload.hostname,
            hostname_normalized=hostname_normalized,
            identity_key=identity_key,
            aliases_json='[]',
            ip_address=payload.ip_address,
            site=payload.site,
            role=payload.role,
            environment=payload.environment,
            collection_method=payload.collection_method,
            metadata_json=metadata_json,
        )
        db.add(row)
        db.flush()
    row.identity_key = build_identity_key(payload.vendor, row.hostname, management_ip=row.ip_address, explicit_device_id=row.id)
    db.commit()
    db.refresh(row)
    return _device_summary(row)


@router.get('/devices', response_model=list[DeviceSummary])
def list_devices(db: Session = Depends(get_db)) -> list[DeviceSummary]:
    return _list_devices(db)


@router.get('/devices/{device_id}', response_model=DeviceSummary)
def get_device(device_id: int, db: Session = Depends(get_db)) -> DeviceSummary:
    row = db.query(Device).filter(Device.id == device_id).order_by(Device.id.asc()).first()
    if not row:
        raise HTTPException(status_code=404, detail=f'Device {device_id} not found')
    return _device_summary(row)


@router.get('/devices/{device_id}/issues', response_model=list[IssueSummary])
def get_device_issues(device_id: int, db: Session = Depends(get_db)) -> list[IssueSummary]:
    service = IssueService(db)
    return [_issue_summary(item) for item in service.list_device_issues(device_id)]


@router.get('/devices/{device_id}/diff', response_model=DiffResponse)
def get_device_diff(device_id: int, from_snapshot_id: int | None = None, to_snapshot_id: int | None = None, db: Session = Depends(get_db)) -> DiffResponse:
    service = DiffService(db)
    try:
        if from_snapshot_id and to_snapshot_id:
            payload = service.diff_between(device_id=device_id, from_snapshot_id=from_snapshot_id, to_snapshot_id=to_snapshot_id)
        else:
            payload = service.diff_latest(device_id=device_id)
        return DiffResponse(**payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get('/runs', response_model=list[ValidationRunSummary])
def list_runs(limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)) -> list[ValidationRunSummary]:
    return _list_runs(db, limit=limit)


@router.get('/runs/{run_id}/findings', response_model=list[Finding])
def get_run_findings(run_id: int, db: Session = Depends(get_db)) -> list[Finding]:
    service = IssueService(db)
    return [Finding(**_finding_to_dict(item)) for item in service.get_run_findings(run_id)]


@router.get('/runs/{run_id}/artifacts', response_model=RunArtifactsResponse)
def get_run_artifacts(run_id: int, db: Session = Depends(get_db)) -> RunArtifactsResponse:
    row = db.query(ValidationRun).filter(ValidationRun.id == run_id).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail=f'Run {run_id} not found')
    return RunArtifactsResponse(
        run_id=row.id,
        vendor=row.vendor,
        hostname=row.hostname,
        status=row.status,
        raw_config_path=row.raw_config_path,
        redacted_config_path=row.redacted_config_path,
        report_json_path=row.report_json_path,
        report_html_path=row.report_html_path,
        config_snapshot_id=row.config_snapshot_id,
        normalized_config_id=row.normalized_config_id,
    )


@router.get('/issues', response_model=list[IssueSummary])
def list_issues(status: str | None = None, db: Session = Depends(get_db)) -> list[IssueSummary]:
    return _list_issues(db, status=status)


@router.get('/issues/{issue_id}', response_model=IssueDetail)
def get_issue(issue_id: int, db: Session = Depends(get_db)) -> IssueDetail:
    issue = IssueService(db).get_issue(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail=f'Issue {issue_id} not found')
    return _issue_detail(issue)


@router.patch('/issues/{issue_id}', response_model=IssueDetail)
def update_issue(issue_id: int, payload: IssueUpdateRequest, db: Session = Depends(get_db)) -> IssueDetail:
    issue = IssueService(db).update_issue(issue_id, **payload.model_dump())
    if not issue:
        raise HTTPException(status_code=404, detail=f'Issue {issue_id} not found')
    return _issue_detail(issue)


@router.get('/export/runs')
def export_runs(db: Session = Depends(get_db)) -> FileResponse:
    path = ExportService(db).export_runs_csv()
    return FileResponse(path, filename=Path(path).name, media_type='text/csv')


@router.get('/export/findings')
def export_findings(db: Session = Depends(get_db)) -> FileResponse:
    path = ExportService(db).export_findings_csv()
    return FileResponse(path, filename=Path(path).name, media_type='text/csv')


def _list_devices(db: Session) -> list[DeviceSummary]:
    rows = db.query(Device).order_by(Device.vendor.asc(), Device.hostname.asc()).all()
    return [_device_summary(row) for row in rows]


def _list_runs(db: Session, limit: int = 50) -> list[ValidationRunSummary]:
    rows = db.query(ValidationRun).order_by(ValidationRun.id.desc()).limit(limit).all()
    return [
        ValidationRunSummary(
            id=row.id,
            vendor=row.vendor,
            hostname=row.hostname,
            status=row.status,
            profile=row.profile,
            source_type=row.source_type,
            run_kind=row.run_kind,
            source_scope=row.source_scope,
            expected_outcome=row.expected_outcome,
            failure_kind=row.failure_kind,
            profile_match_status=row.profile_match_status,
            dataset_name=row.dataset_name,
            is_test_data=row.is_test_data,
            report_json_path=row.report_json_path,
            report_html_path=row.report_html_path,
            raw_config_path=row.raw_config_path,
            redacted_config_path=row.redacted_config_path,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]


def _list_issues(db: Session, status: str | None = None, limit: int = 100) -> list[IssueSummary]:
    service = IssueService(db)
    return [_issue_summary(item) for item in service.list_issues(status=status)[:limit]]


def _device_summary(row: Device) -> DeviceSummary:
    return DeviceSummary(
        id=row.id,
        vendor=row.vendor,
        hostname=row.hostname,
        hostname_normalized=row.hostname_normalized,
        identity_key=row.identity_key,
        aliases=json.loads(row.aliases_json or '[]'),
        ip_address=row.ip_address,
        site=row.site,
        role=row.role,
        environment=row.environment,
        collection_method=row.collection_method,
        metadata=json.loads(row.metadata_json or '{}'),
        last_status=row.last_status,
        last_seen_at=row.last_seen_at.isoformat(),
    )


def _issue_summary(issue: ConfigIssue) -> IssueSummary:
    return IssueSummary(
        id=issue.id,
        device_id=issue.device_id,
        latest_validation_run_id=issue.latest_validation_run_id,
        status=issue.status,
        severity=issue.severity,
        root_cause=issue.root_cause,
        summary=issue.summary,
        assigned_to=issue.assigned_to,
        first_seen_at=issue.first_seen_at.isoformat(),
        last_seen_at=issue.last_seen_at.isoformat(),
        resolved_at=issue.resolved_at.isoformat() if issue.resolved_at else None,
        occurrences_count=issue.occurrences_count,
    )


def _issue_detail(issue: ConfigIssue) -> IssueDetail:
    return IssueDetail(**_issue_summary(issue).model_dump(), issue_key=issue.issue_key, details=issue.details, resolution_comment=issue.resolution_comment, metadata=json.loads(issue.metadata_json or '{}'))


def _finding_to_dict(item) -> dict:
    return {
        'code': item.code,
        'severity': item.severity,
        'message': item.message,
        'path': item.path,
        'category': item.category,
        'recommendation': item.recommendation,
        'remediation_example': item.remediation_example,
        'rule_source': item.rule_source,
        'rule_version': item.rule_version,
        'confidence': item.confidence,
    }
