from __future__ import annotations

from time import perf_counter

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Query, Session

from app.core.models import ConfigIssue, MetricsSnapshot, ValidationFinding, ValidationRun


class Timer:
    def __enter__(self):
        self.start = perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.elapsed = perf_counter() - self.start


def _operational_run_filters():
    return [
        ValidationRun.run_kind.notin_(['dataset', 'regression', 'negative']),
        ValidationRun.source_scope.notin_(['dataset', 'sample', 'partial', 'raw']),
        ValidationRun.is_test_data.is_(False),
    ]


def _dataset_run_filters():
    return [
        or_(
            ValidationRun.run_kind.in_(['dataset', 'regression']),
            ValidationRun.source_scope.in_(['dataset', 'sample', 'partial', 'raw']),
            ValidationRun.is_test_data.is_(True),
        )
    ]


def _apply_scope_runs(query: Query, scope: str) -> Query:
    if scope == 'operational':
        return query.filter(*_operational_run_filters())
    if scope == 'dataset':
        return query.filter(*_dataset_run_filters())
    if scope == 'test':
        return query.filter(ValidationRun.is_test_data.is_(True))
    return query


def _apply_scope_metrics(query: Query, scope: str) -> Query:
    query = query.join(ValidationRun, ValidationRun.id == MetricsSnapshot.validation_run_id)
    return _apply_scope_runs(query, scope)


def build_summary(db: Session, scope: str = 'all') -> dict:
    base_query = _apply_scope_runs(db.query(ValidationRun), scope)
    total_runs = base_query.count()
    passed_runs = base_query.filter(ValidationRun.status == 'passed').count()
    failed_runs = base_query.filter(ValidationRun.status == 'failed').count()
    unexpected_failed_runs = base_query.filter(
        ValidationRun.status == 'failed',
        ValidationRun.expected_outcome != 'failed',
    ).count()

    vendor_rows = (
        _apply_scope_runs(
            db.query(
                ValidationRun.vendor,
                func.count(ValidationRun.id).label('total_runs'),
                func.sum(case((ValidationRun.status == 'passed', 1), else_=0)).label('passed_runs'),
                func.sum(case((ValidationRun.status == 'failed', 1), else_=0)).label('failed_runs'),
                func.avg(MetricsSnapshot.execution_time_sec).label('avg_execution_time_sec'),
            ).outerjoin(MetricsSnapshot, MetricsSnapshot.validation_run_id == ValidationRun.id),
            scope,
        )
        .group_by(ValidationRun.vendor)
        .all()
    )
    by_vendor = [
        {
            'vendor': vendor,
            'total_runs': int(total or 0),
            'passed_runs': int(passed or 0),
            'failed_runs': int(failed or 0),
            'avg_execution_time_sec': round(float(avg_exec or 0.0), 6),
        }
        for vendor, total, passed, failed, avg_exec in vendor_rows
    ]

    code_rows = (
        _apply_scope_runs(
            db.query(ValidationFinding.code, func.count(ValidationFinding.id).label('total'))
            .join(ValidationRun, ValidationRun.id == ValidationFinding.validation_run_id),
            scope,
        )
        .group_by(ValidationFinding.code)
        .order_by(func.count(ValidationFinding.id).desc(), ValidationFinding.code.asc())
        .all()
    )
    by_code = [{'code': code, 'total': int(total or 0)} for code, total in code_rows]

    failure_kind_rows = (
        _apply_scope_runs(
            db.query(ValidationRun.failure_kind, func.count(ValidationRun.id).label('total')),
            scope,
        )
        .filter(ValidationRun.failure_kind.isnot(None))
        .group_by(ValidationRun.failure_kind)
        .order_by(func.count(ValidationRun.id).desc(), ValidationRun.failure_kind.asc())
        .all()
    )
    by_failure_kind = [
        {'failure_kind': kind, 'total': int(total or 0)}
        for kind, total in failure_kind_rows
    ]

    metric_query = _apply_scope_metrics(db.query(MetricsSnapshot), scope)
    latest_metric = metric_query.order_by(MetricsSnapshot.id.desc()).first()
    avg_exec = metric_query.with_entities(func.avg(MetricsSnapshot.execution_time_sec)).scalar()
    avg_coverage = metric_query.with_entities(func.avg(MetricsSnapshot.coverage_ratio)).scalar()
    open_issues = db.query(func.count(ConfigIssue.id)).filter(ConfigIssue.status.in_(['open', 'acknowledged', 'in_progress'])).scalar() or 0

    return {
        'scope': scope,
        'total_runs': int(total_runs),
        'passed_runs': int(passed_runs),
        'failed_runs': int(failed_runs),
        'unexpected_failed_runs': int(unexpected_failed_runs),
        'pass_rate': round((passed_runs / total_runs), 4) if total_runs else 0.0,
        'avg_execution_time_sec': round(float(avg_exec or 0.0), 6),
        'avg_coverage_ratio': round(float(avg_coverage or 0.0), 6),
        'latest_run_id': latest_metric.validation_run_id if latest_metric else None,
        'open_issues': int(open_issues),
        'by_vendor': by_vendor,
        'by_code': by_code,
        'by_failure_kind': by_failure_kind,
    }


def render_prometheus_metrics(db: Session) -> str:
    summary = build_summary(db, scope='operational')
    lines = [
        '# HELP ncv_total_runs Total validation runs',
        '# TYPE ncv_total_runs gauge',
        f"ncv_total_runs {summary['total_runs']}",
        '# HELP ncv_passed_runs Passed validation runs',
        '# TYPE ncv_passed_runs gauge',
        f"ncv_passed_runs {summary['passed_runs']}",
        '# HELP ncv_failed_runs Failed validation runs',
        '# TYPE ncv_failed_runs gauge',
        f"ncv_failed_runs {summary['failed_runs']}",
        '# HELP ncv_unexpected_failed_runs Unexpected failed validation runs',
        '# TYPE ncv_unexpected_failed_runs gauge',
        f"ncv_unexpected_failed_runs {summary['unexpected_failed_runs']}",
        '# HELP ncv_open_issues Open configuration issues',
        '# TYPE ncv_open_issues gauge',
        f"ncv_open_issues {summary['open_issues']}",
        '# HELP ncv_avg_execution_time_seconds Average validation execution time',
        '# TYPE ncv_avg_execution_time_seconds gauge',
        f"ncv_avg_execution_time_seconds {summary['avg_execution_time_sec']}",
    ]
    for row in summary['by_vendor']:
        lines.append(f'ncv_runs_by_vendor{{vendor="{row["vendor"]}"}} {row["total_runs"]}')
        lines.append(f'ncv_failed_by_vendor{{vendor="{row["vendor"]}"}} {row["failed_runs"]}')
    for row in summary['by_code']:
        lines.append(f'ncv_findings_by_code{{code="{row["code"]}"}} {row["total"]}')
    for row in summary['by_failure_kind']:
        lines.append(f'ncv_failed_by_kind{{kind="{row["failure_kind"]}"}} {row["total"]}')
    return "\n".join(lines) + "\n"
