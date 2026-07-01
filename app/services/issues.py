from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.models import ConfigIssue, IssueOccurrence, ValidationFinding, ValidationRun


class IssueService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def sync_for_run(self, *, run: ValidationRun, findings: list[dict[str, Any]]) -> int | None:
        if run.status == 'passed':
            self._close_open_issues_for_device(run.device_id, run.id)
            return None
        if not findings:
            return None
        issue_key = self._build_issue_key(run, findings)
        root_cause = self._root_cause(findings, run.failure_kind)
        severity = self._issue_severity(findings)
        summary = self._summary(run, findings)
        details = json.dumps(findings, ensure_ascii=False)
        issue = self.db.query(ConfigIssue).filter(ConfigIssue.issue_key == issue_key).one_or_none()
        now = datetime.now(UTC).replace(tzinfo=None)
        if issue:
            issue.device_id = run.device_id
            issue.latest_validation_run_id = run.id
            issue.last_seen_at = now
            issue.occurrences_count += 1
            issue.status = 'open'
            issue.severity = severity
            issue.root_cause = root_cause
            issue.summary = summary
            issue.details = details
            issue.resolved_at = None
        else:
            issue = ConfigIssue(
                device_id=run.device_id,
                latest_validation_run_id=run.id,
                issue_key=issue_key,
                status='open',
                severity=severity,
                root_cause=root_cause,
                summary=summary,
                details=details,
                first_seen_at=now,
                last_seen_at=now,
                occurrences_count=1,
                metadata_json=json.dumps({'failure_kind': run.failure_kind}, ensure_ascii=False),
            )
            self.db.add(issue)
            self.db.flush()
        self.db.add(IssueOccurrence(issue_id=issue.id, validation_run_id=run.id))
        return issue.id

    def list_issues(self, *, status: str | None = None) -> list[ConfigIssue]:
        query = self.db.query(ConfigIssue)
        if status:
            query = query.filter(ConfigIssue.status == status)
        return query.order_by(ConfigIssue.last_seen_at.desc(), ConfigIssue.id.desc()).all()

    def get_issue(self, issue_id: int) -> ConfigIssue | None:
        return self.db.query(ConfigIssue).filter(ConfigIssue.id == issue_id).one_or_none()

    def list_device_issues(self, device_id: int) -> list[ConfigIssue]:
        return self.db.query(ConfigIssue).filter(ConfigIssue.device_id == device_id).order_by(ConfigIssue.last_seen_at.desc()).all()

    def update_issue(self, issue_id: int, **updates: Any) -> ConfigIssue | None:
        issue = self.get_issue(issue_id)
        if not issue:
            return None
        for key, value in updates.items():
            if hasattr(issue, key) and value is not None:
                setattr(issue, key, value)
        if updates.get('status') == 'fixed' and issue.resolved_at is None:
            issue.resolved_at = datetime.now(UTC).replace(tzinfo=None)
        self.db.commit()
        self.db.refresh(issue)
        return issue

    def get_run_findings(self, run_id: int) -> list[ValidationFinding]:
        return self.db.query(ValidationFinding).filter(ValidationFinding.validation_run_id == run_id).order_by(ValidationFinding.id.asc()).all()

    def _close_open_issues_for_device(self, device_id: int | None, run_id: int | None = None) -> None:
        if not device_id:
            return
        now = datetime.now(UTC).replace(tzinfo=None)
        rows = self.db.query(ConfigIssue).filter(ConfigIssue.device_id == device_id, ConfigIssue.status.in_(['open', 'acknowledged', 'in_progress'])).all()
        for issue in rows:
            issue.status = 'fixed'
            issue.resolved_at = now
            issue.latest_validation_run_id = run_id or issue.latest_validation_run_id
            issue.resolution_comment = issue.resolution_comment or 'Automatically resolved after successful validation run.'

    @staticmethod
    def _issue_severity(findings: list[dict[str, Any]]) -> str:
        severities = {item.get('severity') for item in findings}
        if 'error' in severities:
            return 'high'
        if 'warning' in severities:
            return 'medium'
        return 'low'

    @staticmethod
    def _root_cause(findings: list[dict[str, Any]], failure_kind: str | None) -> str:
        if failure_kind:
            return failure_kind.replace('failed_', '')
        for item in findings:
            if item.get('category'):
                return str(item['category'])
        return 'validation'

    @staticmethod
    def _summary(run: ValidationRun, findings: list[dict[str, Any]]) -> str:
        top_codes = ', '.join(sorted({item.get('code', 'UNKNOWN') for item in findings})[:3])
        return f'{run.vendor}:{run.hostname} validation issue ({top_codes})'

    @staticmethod
    def _build_issue_key(run: ValidationRun, findings: list[dict[str, Any]]) -> str:
        code_set = '|'.join(sorted({item.get('code', 'UNKNOWN') for item in findings}))
        device_part = f'device:{run.device_id}' if run.device_id is not None else f'host:{run.hostname.lower()}'
        base = f'{run.vendor.lower()}:{device_part}:{run.failure_kind or "failed"}:{code_set}'
        return hashlib.sha256(base.encode('utf-8')).hexdigest()
