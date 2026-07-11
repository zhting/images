"""Minimal in-process task manager for heavy background jobs.

Why not FastAPI BackgroundTasks / ad-hoc threads:
- Heavy jobs (indexing, face clustering, location refinement) previously
  ran on the server's default thread pool, where minute-to-hour work
  starves ordinary request handling.
- Nothing serialized concurrent triggers beyond scattered state checks.

Design: one dedicated daemon worker executes tasks strictly serially —
indexing-class jobs contend for the model, the disk and the vector DB,
so they should never overlap anyway.  Same-name dedupe means a double
click on "start indexing" returns the running task instead of queueing
a second pass.  Cancellation is cooperative via task.cancelled, which
maps 1:1 onto SyncManager's existing stop_check parameter.
"""
import threading
import traceback
import uuid
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue

import logging
logger = logging.getLogger(__name__)


class TaskState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


ACTIVE_STATES = (TaskState.PENDING, TaskState.RUNNING)


@dataclass
class Task:
    id: str
    name: str
    state: TaskState = TaskState.PENDING
    progress: float = 0.0          # 0..1
    message: str = ""
    error: str = ""
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    def report(self, progress: float = None, message: str = None):
        if progress is not None:
            self.progress = max(0.0, min(1.0, float(progress)))
        if message is not None:
            self.message = message

    def cancel(self):
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "state": self.state.value,
                "progress": round(self.progress, 4), "message": self.message,
                "error": self.error}


class TaskRunner:
    MAX_FINISHED_KEPT = 50

    def __init__(self):
        self._q: Queue = Queue()
        self._lock = threading.Lock()
        self.tasks: dict = {}          # id -> Task, insertion-ordered
        self._worker = threading.Thread(target=self._loop, daemon=True,
                                        name="task-runner")
        self._worker.start()

    # ------------------------------------------------------------------

    def submit(self, name: str, fn) -> Task:
        """Queue *fn(task)* for execution. If a task with the same name is
        already pending/running, return it instead (dedupe)."""
        with self._lock:
            for t in self.tasks.values():
                if t.name == name and t.state in ACTIVE_STATES:
                    return t
            task = Task(id=uuid.uuid4().hex[:8], name=name)
            self.tasks[task.id] = task
            self._trim_finished()
        self._q.put((task, fn))
        return task

    def get(self, task_id: str):
        return self.tasks.get(task_id)

    def cancel(self, task_id: str) -> bool:
        t = self.tasks.get(task_id)
        if t and t.state in ACTIVE_STATES:
            t.cancel()
            return True
        return False

    def list(self) -> list:
        return [t.to_dict() for t in self.tasks.values()]

    def active(self):
        for t in self.tasks.values():
            if t.state in ACTIVE_STATES:
                return t
        return None

    # ------------------------------------------------------------------

    def _trim_finished(self):
        finished = [tid for tid, t in self.tasks.items()
                    if t.state not in ACTIVE_STATES]
        overflow = len(finished) - self.MAX_FINISHED_KEPT
        for tid in finished[:max(0, overflow)]:
            self.tasks.pop(tid, None)

    def _loop(self):
        while True:
            task, fn = self._q.get()
            if task.cancelled:
                task.state = TaskState.CANCELLED
                continue
            task.state = TaskState.RUNNING
            try:
                fn(task)
                task.state = (TaskState.CANCELLED if task.cancelled
                              else TaskState.DONE)
                if task.state is TaskState.DONE:
                    task.progress = 1.0
            except Exception:
                task.state = TaskState.FAILED
                task.error = traceback.format_exc()
                logger.error(f"[TaskRunner] task '{task.name}' failed:\n{task.error}")


# Process-wide singleton
runner = TaskRunner()
