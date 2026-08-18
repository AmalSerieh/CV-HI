"""Thread-safe, in-memory temporary analysis state."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import UUID, uuid4


class AnalysisNotFound(KeyError):
    pass


class TooManyAnalyses(RuntimeError):
    pass


@dataclass
class JobRecord:
    id: UUID
    created_at: datetime
    updated_at: datetime
    status: str
    stage: str
    directory: Path
    document_name: str
    result: dict[str, Any] | None = None
    error: dict[str, str] | None = None
    completed_stages: list[str] = field(default_factory=list)
    review_state: Any | None = None
    deleted: bool = False

    def public_status(self) -> dict[str, Any]:
        return {
            "analysis_id": str(self.id),
            "status": self.status,
            "stage": self.stage,
            "completed_stages": list(self.completed_stages),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "result_available": self.status == "completed" and self.result is not None,
            "error": self.error,
        }


class JobStore:
    def __init__(self, ttl_minutes: int, cleanup: Callable[[Path], None]) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        self._cleanup = cleanup
        self._jobs: dict[UUID, JobRecord] = {}
        self._lock = RLock()

    def create(self, directory: Path, document_name: str) -> JobRecord:
        self.cleanup_expired()
        now = datetime.now(timezone.utc)
        record = JobRecord(
            id=uuid4(),
            created_at=now,
            updated_at=now,
            status="queued",
            stage="queued",
            directory=directory,
            document_name=document_name,
            completed_stages=["uploading", "validating_document"],
        )
        with self._lock:
            self._jobs[record.id] = record
        return record

    def get(self, analysis_id: UUID) -> JobRecord:
        self.cleanup_expired()
        with self._lock:
            record = self._jobs.get(analysis_id)
            if record is None or record.deleted:
                raise AnalysisNotFound(str(analysis_id))
            return record

    def update_stage(self, analysis_id: UUID, stage: str, *, completed: str | None = None) -> None:
        with self._lock:
            record = self._jobs.get(analysis_id)
            if record is None or record.deleted:
                return
            record.status = "running"
            record.stage = stage
            if completed and completed not in record.completed_stages:
                record.completed_stages.append(completed)
            record.updated_at = datetime.now(timezone.utc)

    def complete(self, analysis_id: UUID, result: dict[str, Any]) -> None:
        with self._lock:
            record = self._jobs.get(analysis_id)
            if record is None or record.deleted:
                return
            record.result = result
            record.status = "completed"
            record.stage = "completed"
            for stage in ("running_pipeline", "validating_final_report", "completed"):
                if stage not in record.completed_stages:
                    record.completed_stages.append(stage)
            record.updated_at = datetime.now(timezone.utc)

    def fail(self, analysis_id: UUID, code: str, message: str) -> None:
        with self._lock:
            record = self._jobs.get(analysis_id)
            if record is None or record.deleted:
                return
            record.status = "failed"
            record.stage = "failed"
            record.error = {"code": code, "message": message}
            record.updated_at = datetime.now(timezone.utc)

    def get_or_create_review_state(self, analysis_id: UUID, factory: Callable[[], Any]) -> Any:
        """Return an isolated copy of state that expires with its analysis."""

        self.cleanup_expired()
        with self._lock:
            record = self._jobs.get(analysis_id)
            if record is None or record.deleted:
                raise AnalysisNotFound(str(analysis_id))
            if record.review_state is None:
                record.review_state = deepcopy(factory())
            return deepcopy(record.review_state)

    def update_review_state(
        self,
        analysis_id: UUID,
        factory: Callable[[], Any],
        updater: Callable[[Any], Any],
    ) -> Any:
        """Validate and commit a review update atomically under the store lock."""

        self.cleanup_expired()
        with self._lock:
            record = self._jobs.get(analysis_id)
            if record is None or record.deleted:
                raise AnalysisNotFound(str(analysis_id))
            current = record.review_state
            candidate = deepcopy(current if current is not None else factory())
            updated = updater(candidate)
            record.review_state = deepcopy(updated)
            record.updated_at = datetime.now(timezone.utc)
            return deepcopy(updated)

    def delete(self, analysis_id: UUID) -> None:
        with self._lock:
            record = self._jobs.pop(analysis_id, None)
            if record is None:
                raise AnalysisNotFound(str(analysis_id))
            record.deleted = True
            should_cleanup = record.status not in {"running"}
        if should_cleanup:
            self._cleanup(record.directory)

    def cleanup_expired(self) -> int:
        now = datetime.now(timezone.utc)
        expired: list[JobRecord] = []
        with self._lock:
            for analysis_id, record in list(self._jobs.items()):
                if record.status in {"queued", "running"}:
                    continue
                if now - record.updated_at >= self._ttl:
                    expired.append(self._jobs.pop(analysis_id))
        for record in expired:
            record.deleted = True
            self._cleanup(record.directory)
        return len(expired)

    def clear(self) -> None:
        with self._lock:
            records = list(self._jobs.values())
            self._jobs.clear()
        for record in records:
            record.deleted = True
            self._cleanup(record.directory)
