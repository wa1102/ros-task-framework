"""
HTTP-to-ROS task scheduling bridge.

Provides a FastAPI server that accepts task requests over HTTP and
dispatches them as ROS-backed subprocesses.  Task lifecycle (start →
execute → cleanup) is managed end-to-end by this module.
"""

from __future__ import annotations

import logging
import os
import signal
import socket
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ros_task_framework")

# ---------------------------------------------------------------------------
# ROS (optional) — try to import but never crash
# ---------------------------------------------------------------------------

ROS_AVAILABLE = False
_ROSPY_IMPORT_ERROR: Optional[str] = None

try:
    import rospy
    from std_msgs.msg import String

    ROS_AVAILABLE = True
except Exception as exc:
    _ROSPY_IMPORT_ERROR = str(exc)

# ---------------------------------------------------------------------------
# Project settings
# ---------------------------------------------------------------------------

from settings import (
    CATKIN_WS,
    DEFAULT_LOG_TAIL_LINES,
    LOG_DIR,
    MAX_TASK_HISTORY,
    SERVER_HOST,
    SERVER_PORT,
    TASKS,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROS_MASTER_HOST = "127.0.0.1"
ROS_MASTER_PORT = 11311
ROS_MASTER_STARTUP_TIMEOUT = 10.0  # seconds
ROS_MASTER_POLL_INTERVAL = 0.5  # seconds

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class TaskStatus(str, Enum):
    IDLE = "idle"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"


class TaskRequest(BaseModel):
    task_type: str
    task_id: str


@dataclass
class TaskState:
    """Mutable state for one task run."""

    process: subprocess.Popen
    task_type: str
    task_id: str
    log_path: str
    status: TaskStatus = TaskStatus.EXECUTING
    start_ts: float = field(default_factory=time.time)
    end_ts: Optional[float] = None
    returncode: Optional[int] = None
    pid: Optional[int] = field(default=None)

    def __post_init__(self) -> None:
        self.pid = self.process.pid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iso_ts() -> str:
    """Return an ISO-8601 timestamp string (UTC) for log file naming."""
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def read_tail(path: str, n: int = DEFAULT_LOG_TAIL_LINES) -> list[str]:
    """Return the last *n* lines of *path* as a list of strings.

    Returns a single-element list with an error description when the file
    cannot be read.
    """
    if not path or not os.path.exists(path):
        return [f"[tail] log not found: {path}"]
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
        return lines[-n:] if len(lines) > n else lines
    except Exception as exc:
        return [f"[tail] read error: {exc}"]


def _is_roscore_running(host: str = ROS_MASTER_HOST, port: int = ROS_MASTER_PORT) -> bool:
    """Check whether a ROS Master is reachable at *host:port*."""
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def _start_roscore() -> None:
    """Start ``roscore`` if it isn't already running.

    Raises :class:`RuntimeError` when roscore does not become reachable
    within *ROS_MASTER_STARTUP_TIMEOUT* seconds.
    """
    if _is_roscore_running():
        logger.info("ROS Master is already running.")
        return

    logger.info("ROS Master not found — starting roscore …")
    subprocess.Popen(
        ["roscore"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    deadline = time.time() + ROS_MASTER_STARTUP_TIMEOUT
    while time.time() < deadline:
        if _is_roscore_running():
            logger.info("roscore started successfully.")
            return
        time.sleep(ROS_MASTER_POLL_INTERVAL)

    raise RuntimeError(
        f"roscore did not start within {ROS_MASTER_STARTUP_TIMEOUT:.0f} s"
    )


def spawn_task(script_path: str, task_id: str, cwd: str = CATKIN_WS) -> tuple[subprocess.Popen, str]:
    """Launch *script_path* in a new process group and return ``(process, log_path)``.

    The script runs inside ``bash -lc`` so that ROS environment variables
    are sourced correctly in systemd / headless contexts.  stdout and
    stderr are written directly to a timestamped log file (no pipes — the
    log is always flushed to disk and never blocks the child).
    """
    ts = _iso_ts()
    stem = Path(script_path).stem
    log_path = str(LOG_DIR / f"{stem}_{task_id}_{ts}.log")

    cmd = ["bash", "-lc", f"bash {shlex.quote(script_path)} {shlex.quote(task_id)}"]

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    # Open the log file *before* spawning so the child inherits the fd.
    logf = open(log_path, "a", buffering=1)  # line-buffered

    proc = subprocess.Popen(
        cmd,
        stdout=logf,
        stderr=subprocess.STDOUT,
        cwd=cwd,
        env=env,
        start_new_session=True,
    )

    # The child has its own copy of the file descriptor — we can close ours.
    logf.close()

    logger.info("Spawned pid=%d  task_id=%s  script=%s  log=%s", proc.pid, task_id, script_path, log_path)
    return proc, log_path


# Add missing import (used in spawn_task)
import shlex  # noqa: E402

# ---------------------------------------------------------------------------
# Global state (singleton — one server, one robot)
# ---------------------------------------------------------------------------


class RobotStateManager:
    """Holds the active task and a bounded history of completed tasks.

    When ROS is available a status publisher is created lazily on first
    use so that server startup is never gated on roscore availability.
    """

    def __init__(self) -> None:
        self.active_task: Optional[TaskState] = None
        self._history: dict[str, TaskState] = {}
        self._history_order: deque[str] = deque()

        # ROS publisher — created lazily
        self._status_pub = None
        self._ros_initialised = False

    # -- ROS ---------------------------------------------------------------

    def _ensure_ros(self) -> None:
        """One-shot initialisation of the ROS node & publisher."""
        if self._ros_initialised or not ROS_AVAILABLE:
            return
        try:
            _start_roscore()
            rospy.init_node("robot_http_bridge", anonymous=True, disable_signals=True)
            self._status_pub = rospy.Publisher("/robot/api_status", String, queue_size=10)
            self._ros_initialised = True
            logger.info("ROS publisher ready on /robot/api_status")
        except Exception as exc:
            logger.warning("ROS initialisation failed — ROS features disabled: %s", exc)
            self._ros_initialised = True  # don't retry

    # -- History -----------------------------------------------------------

    def _archive(self, task: TaskState) -> None:
        """Push a finished task into the bounded history."""
        tid = task.task_id
        self._history[tid] = task
        self._history_order.append(tid)
        while len(self._history_order) > MAX_TASK_HISTORY:
            evicted = self._history_order.popleft()
            self._history.pop(evicted, None)

    def lookup_history(self, task_id: str) -> Optional[TaskState]:
        """Return a finished task by id, or ``None``."""
        return self._history.get(task_id)

    # -- Tick --------------------------------------------------------------

    def tick(self) -> TaskStatus:
        """Poll the active subprocess and update state.

        Returns the *global* status — ``executing`` while a task is
        running, ``idle`` otherwise.
        """
        global_status = TaskStatus.IDLE
        active = self.active_task

        if active is None or active.process is None:
            return global_status

        ret = active.process.poll()

        if ret is None:
            # Still running
            active.status = TaskStatus.EXECUTING
            global_status = TaskStatus.EXECUTING
        else:
            # Finished
            active.returncode = ret
            active.end_ts = time.time()
            active.status = TaskStatus.SUCCESS if ret == 0 else TaskStatus.FAILED
            elapsed = active.end_ts - active.start_ts
            logger.info(
                "Task %s finished: status=%s  returncode=%d  duration=%.1fs",
                active.task_id,
                active.status.value,
                ret,
                elapsed,
            )
            self._archive(active)
            self.active_task = None

        # Publish via ROS (best-effort)
        self._publish_status(global_status)
        return global_status

    def _publish_status(self, global_status: TaskStatus) -> None:
        """Best-effort ROS status publication."""
        if not ROS_AVAILABLE or self._status_pub is None:
            return
        try:
            if not rospy.is_shutdown():
                active_id = self.active_task.task_id if self.active_task else "None"
                self._status_pub.publish(f"{global_status.value}:{active_id}")
        except Exception:
            pass

    # -- Lifecycle ---------------------------------------------------------

    def _kill_active(self) -> None:
        """Send SIGINT (and SIGKILL as fallback) to the active task's process group."""
        if self.active_task is None or self.active_task.process is None:
            return
        proc = self.active_task.process
        pid = proc.pid
        if pid is None:
            return
        try:
            pgid = os.getpgid(pid)
            logger.info("Sending SIGINT to process group %d …", pgid)
            os.killpg(pgid, signal.SIGINT)
            try:
                proc.wait(timeout=3)
                return
            except subprocess.TimeoutExpired:
                logger.warning("SIGINT timed out — sending SIGKILL to pg %d", pgid)
                os.killpg(pgid, signal.SIGKILL)
                proc.wait(timeout=3)
        except ProcessLookupError:
            pass  # already gone
        except Exception as exc:
            logger.error("Error killing task %s: %s", self.active_task.task_id, exc)


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Robot Task Scheduler",
    version="1.1.0",
    description="HTTP-based task scheduling service for ROS robots.",
)

state = RobotStateManager()

# ---------------------------------------------------------------------------
# Signal handling (graceful shutdown)
# ---------------------------------------------------------------------------

_shutdown_requested = False


def _on_shutdown_signal(signum: int, _frame: object) -> None:
    global _shutdown_requested
    sig_name = signal.Signals(signum).name
    logger.info("Received %s — shutting down gracefully …", sig_name)
    _shutdown_requested = True
    state._kill_active()
    sys.exit(0)


signal.signal(signal.SIGINT, _on_shutdown_signal)
signal.signal(signal.SIGTERM, _on_shutdown_signal)

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/")
async def root() -> dict:
    """Health-check endpoint."""
    return {
        "service": "ROS Task Framework",
        "version": app.version,
        "ros_available": ROS_AVAILABLE,
    }


@app.post("/start_task")
async def start_task(task: TaskRequest) -> dict:
    """Start a robot task.

    Rejects the request when another task is already executing (only one
    task may run at a time).
    """
    state._ensure_ros()
    state.tick()

    # --- reject concurrent execution ---
    if state.active_task is not None:
        current = state.active_task
        logger.warning(
            "Rejected task %s — task %s is still executing (pid=%s)",
            task.task_id,
            current.task_id,
            current.pid,
        )
        return {
            "status": TaskStatus.EXECUTING.value,
            "message": f"Rejected: task '{current.task_id}' is still running.",
            "current_task_id": current.task_id,
            "current_log_path": current.log_path,
            "pid": current.pid,
        }

    # --- validate ---
    if task.task_type not in TASKS:
        known = list(TASKS.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown task type '{task.task_type}'. Known types: {known}",
        )

    script_path = TASKS[task.task_type]
    if not os.path.exists(script_path):
        raise HTTPException(
            status_code=500,
            detail=f"Script not found for task '{task.task_type}': {script_path}",
        )

    # --- launch ---
    try:
        proc, log_path = spawn_task(script_path, task.task_id)
    except Exception as exc:
        logger.exception("Failed to spawn task %s", task.task_id)
        raise HTTPException(status_code=500, detail=f"Failed to start task: {exc}")

    state.active_task = TaskState(
        process=proc,
        task_type=task.task_type,
        task_id=task.task_id,
        log_path=log_path,
    )

    logger.info("Task %s (%s) started — pid=%d", task.task_id, task.task_type, proc.pid)
    return {
        "status": TaskStatus.EXECUTING.value,
        "message": f"Started {task.task_type}",
        "task_id": task.task_id,
        "pid": proc.pid,
        "log_path": log_path,
    }


@app.get("/status")
async def get_status(
    task_id: Optional[str] = Query(None),
    log_tail_lines: int = Query(DEFAULT_LOG_TAIL_LINES, ge=1, le=500),
) -> dict:
    """Query system status or a specific task's status."""
    state._ensure_ros()
    state.tick()

    # --- query by task_id ---
    if task_id:
        # Check active task first
        if state.active_task and state.active_task.task_id == task_id:
            t = state.active_task
            return {
                "task_id": task_id,
                "status": t.status.value,
                "type": t.task_type,
                "pid": t.pid,
                "log_path": t.log_path,
                "returncode": None,
                "log_tail": read_tail(t.log_path, log_tail_lines),
            }

        # Fall back to history
        hist = state.lookup_history(task_id)
        if hist is not None:
            duration = (hist.end_ts - hist.start_ts) if (hist.end_ts and hist.start_ts) else None
            return {
                "task_id": task_id,
                "status": hist.status.value,
                "type": hist.task_type,
                "pid": None,
                "log_path": hist.log_path,
                "returncode": hist.returncode,
                "duration_s": round(duration, 1) if duration else None,
                "log_tail": read_tail(hist.log_path, log_tail_lines),
            }

        raise HTTPException(
            status_code=404,
            detail=f"Task '{task_id}' not found (history size: {MAX_TASK_HISTORY}).",
        )

    # --- global status ---
    if state.active_task:
        t = state.active_task
        return {
            "global_status": TaskStatus.EXECUTING.value,
            "active_task_id": t.task_id,
            "pid": t.pid,
            "log_path": t.log_path,
            "message": "A task is currently executing.",
            "log_tail": read_tail(t.log_path, log_tail_lines),
        }

    return {
        "global_status": TaskStatus.IDLE.value,
        "active_task_id": None,
        "message": "System is idle.",
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Starting ROS Task Framework server on %s:%d …", SERVER_HOST, SERVER_PORT)
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
