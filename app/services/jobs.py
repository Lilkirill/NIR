from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Callable
from uuid import uuid4

from fastapi import BackgroundTasks


@dataclass
class JobRecord:
    job_id: str
    status: str
    submitted_at: str
    finished_at: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()

    def submit(self, background_tasks: BackgroundTasks, fn: Callable[..., dict[str, Any]], *args: Any, **kwargs: Any) -> JobRecord:
        job_id = str(uuid4())
        record = JobRecord(job_id=job_id, status='queued', submitted_at=datetime.now(UTC).isoformat())
        with self._lock:
            self._jobs[job_id] = record
        background_tasks.add_task(self._run, job_id, fn, *args, **kwargs)
        return record

    def _run(self, job_id: str, fn: Callable[..., dict[str, Any]], *args: Any, **kwargs: Any) -> None:
        with self._lock:
            self._jobs[job_id].status = 'running'
        try:
            result = fn(*args, **kwargs)
            with self._lock:
                rec = self._jobs[job_id]
                rec.status = 'completed'
                rec.result = result
                rec.finished_at = datetime.now(UTC).isoformat()
        except Exception as exc:  # pragma: no cover - defensive path
            with self._lock:
                rec = self._jobs[job_id]
                rec.status = 'failed'
                rec.error = str(exc)
                rec.finished_at = datetime.now(UTC).isoformat()

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)


job_store = JobStore()
