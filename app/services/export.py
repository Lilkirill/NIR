from __future__ import annotations

import csv
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.models import ValidationFinding, ValidationRun


class ExportService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def export_runs_csv(self) -> str:
        path = settings.export_path / f'runs_{datetime.now(UTC).strftime("%Y%m%d_%H%M%S")}.csv'
        rows = self.db.query(ValidationRun).order_by(ValidationRun.id.desc()).all()
        with path.open('w', encoding='utf-8', newline='') as fh:
            writer = csv.writer(fh)
            writer.writerow([
                'id', 'vendor', 'hostname', 'status', 'profile', 'source_type', 'run_kind', 'source_scope', 'expected_outcome',
                'failure_kind', 'profile_match_status', 'dataset_name', 'is_test_data', 'raw_config_path', 'report_json_path', 'created_at',
            ])
            for row in rows:
                writer.writerow([
                    row.id, row.vendor, row.hostname, row.status, row.profile, row.source_type, row.run_kind, row.source_scope,
                    row.expected_outcome, row.failure_kind, row.profile_match_status, row.dataset_name, row.is_test_data,
                    row.raw_config_path, row.report_json_path, row.created_at.isoformat(),
                ])
        return str(path)

    def export_findings_csv(self) -> str:
        path = settings.export_path / f'findings_{datetime.now(UTC).strftime("%Y%m%d_%H%M%S")}.csv'
        rows = self.db.query(ValidationFinding).order_by(ValidationFinding.id.desc()).all()
        with path.open('w', encoding='utf-8', newline='') as fh:
            writer = csv.writer(fh)
            writer.writerow([
                'id', 'validation_run_id', 'code', 'severity', 'category', 'message', 'path',
                'recommendation', 'remediation_example', 'rule_source', 'rule_version', 'confidence', 'created_at',
            ])
            for row in rows:
                writer.writerow([
                    row.id, row.validation_run_id, row.code, row.severity, row.category, row.message, row.path,
                    row.recommendation, row.remediation_example, row.rule_source, row.rule_version, row.confidence,
                    row.created_at.isoformat(),
                ])
        return str(path)
