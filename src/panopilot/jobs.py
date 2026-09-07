"""Background job orchestration for PanoPilot desktop work.

Jobs are intentionally GUI-framework agnostic.  Worker threads publish immutable
snapshots that the Qt organizer polls on the GUI thread.  This keeps Qt objects
out of worker threads while allowing preview preparation and final export to run
without monopolizing the desktop event loop.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import Event, Lock
import time
import traceback


class JobCancelled(RuntimeError):
    """Raised at a cooperative cancellation boundary."""


class CancellationToken:
    def __init__(self):
        self._event = Event()

    def cancel(self):
        self._event.set()

    @property
    def is_cancelled(self):
        return self._event.is_set()

    def check(self):
        if self.is_cancelled:
            raise JobCancelled("Background job cancelled")


@dataclass(frozen=True)
class JobSnapshot:
    key: str
    title: str
    state: str
    message: str
    created_at: float
    started_at: float | None
    finished_at: float | None
    progress_event: dict
    result: object = None
    error: BaseException | None = None
    traceback_text: str | None = None

    @property
    def active(self):
        return self.state in ("queued", "running", "cancelling")

    @property
    def terminal(self):
        return self.state in ("succeeded", "failed", "cancelled")


@dataclass
class _JobRecord:
    key: str
    title: str
    token: CancellationToken
    state: str = "queued"
    message: str = "Queued"
    created_at: float = field(default_factory=time.monotonic)
    started_at: float | None = None
    finished_at: float | None = None
    progress_event: dict = field(default_factory=dict)
    result: object = None
    error: BaseException | None = None
    traceback_text: str | None = None
    lock: Lock = field(default_factory=Lock)

    def snapshot(self):
        with self.lock:
            return JobSnapshot(
                key=self.key,
                title=self.title,
                state=self.state,
                message=self.message,
                created_at=self.created_at,
                started_at=self.started_at,
                finished_at=self.finished_at,
                progress_event=dict(self.progress_event),
                result=self.result,
                error=self.error,
                traceback_text=self.traceback_text,
            )


class JobContext:
    def __init__(self, record: _JobRecord):
        self._record = record
        self.token = record.token

    @property
    def cancelled(self):
        return self.token.is_cancelled

    def check_cancelled(self):
        self.token.check()

    def progress(self, event):
        self.check_cancelled()
        if isinstance(event, dict):
            payload = dict(event)
        else:
            payload = {
                "stage": "working",
                "message": str(event),
            }
        message = str(payload.get("message") or "Working…")
        with self._record.lock:
            self._record.progress_event = payload
            self._record.message = message


class BackgroundJobManager:
    """Small bounded worker pool with cooperative cancellation and polling."""

    def __init__(self, *, max_workers=2):
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, int(max_workers)),
            thread_name_prefix="panopilot-job",
        )
        self._records = {}
        self._lock = Lock()
        self._closed = False

    def submit(self, key, title, task, *, replace=False):
        key = str(key)
        title = str(title)
        with self._lock:
            if self._closed:
                raise RuntimeError("BackgroundJobManager is closed")
            previous = self._records.get(key)
            if previous is not None and not replace:
                snapshot = previous.snapshot()
                if snapshot.state not in ("failed", "cancelled"):
                    return snapshot
            if previous is not None and replace:
                previous.token.cancel()
            record = _JobRecord(
                key=key,
                title=title,
                token=CancellationToken(),
            )
            self._records[key] = record

        self._executor.submit(self._run, record, task)
        return record.snapshot()

    @staticmethod
    def _run(record, task):
        with record.lock:
            if record.token.is_cancelled:
                record.state = "cancelled"
                record.message = "Cancelled"
                record.finished_at = time.monotonic()
                return
            record.state = "running"
            record.message = "Starting…"
            record.started_at = time.monotonic()

        context = JobContext(record)
        try:
            context.check_cancelled()
            value = task(context)
            context.check_cancelled()
        except JobCancelled as exc:
            with record.lock:
                record.state = "cancelled"
                record.message = "Cancelled"
                record.error = exc
                record.finished_at = time.monotonic()
            return
        except BaseException as exc:
            with record.lock:
                record.state = "failed"
                record.message = str(exc) or exc.__class__.__name__
                record.error = exc
                record.traceback_text = traceback.format_exc()
                record.finished_at = time.monotonic()
            return

        with record.lock:
            record.state = "succeeded"
            record.message = "Ready"
            record.result = value
            record.finished_at = time.monotonic()

    def snapshot(self, key):
        with self._lock:
            record = self._records.get(str(key))
        return record.snapshot() if record is not None else None

    def snapshots(self):
        with self._lock:
            records = list(self._records.values())
        return {
            record.key: record.snapshot()
            for record in records
        }

    def cancel(self, key):
        with self._lock:
            record = self._records.get(str(key))
        if record is None:
            return False
        record.token.cancel()
        with record.lock:
            if record.state in ("queued", "running"):
                record.state = "cancelling"
                record.message = "Cancelling…"
        return True

    def cancel_all(self, *, prefix=None):
        snapshots = self.snapshots()
        count = 0
        for key, snapshot in snapshots.items():
            if prefix is not None and not key.startswith(str(prefix)):
                continue
            if snapshot.active and self.cancel(key):
                count += 1
        return count

    def shutdown(self, *, cancel=True, wait=False):
        with self._lock:
            if self._closed:
                return
            self._closed = True
        if cancel:
            self.cancel_all()
        self._executor.shutdown(
            wait=bool(wait),
            cancel_futures=bool(cancel),
        )
