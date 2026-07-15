import os
import time
import shlex
import socket
import subprocess

from enum import Enum
from pathlib import Path
from collections import deque
from typing import Optional, Dict, Deque, List

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# -----------------------------
# ROS (Optional)
# -----------------------------
ROS_AVAILABLE = False

try:
    import rospy
    from std_msgs.msg import String
    ROS_AVAILABLE = True
except Exception:
    ROS_AVAILABLE = False

# -----------------------------
# Project Config
# -----------------------------
from settings import (
    CATKIN_WS,
    LOG_DIR,
    TASKS,
    DEFAULT_LOG_TAIL_LINES,
)

# -----------------------------
# 数据结构
# -----------------------------
class TaskStatus(str, Enum):
    IDLE = "idle"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"


class TaskRequest(BaseModel):
    task_type: str
    task_id: str


class TaskState:
    def __init__(self, process: subprocess.Popen, task_type: str, task_id: str, log_path: str):
        self.process = process
        self.status = TaskStatus.EXECUTING
        self.task_type = task_type
        self.task_id = task_id
        self.log_path = log_path
        self.start_ts = time.time()
        self.end_ts: Optional[float] = None
        self.returncode: Optional[int] = None


def tail_file(path: str, n: int = 80) -> List[str]:
    """读取文件最后 n 行（失败则返回错误信息）。"""
    try:
        if not path or not os.path.exists(path):
            return [f"[tail] log not found: {path}"]
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = 4096
            data = b""
            while size > 0 and data.count(b"\n") <= n:
                step = min(block, size)
                size -= step
                f.seek(size)
                data = f.read(step) + data
            return data.decode(errors="replace").splitlines()[-n:]
    except Exception as e:
        return [f"[tail error] {e}"]




def is_roscore_running(host="127.0.0.1", port=11311):
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except Exception:
        return False


def ensure_roscore():
    if is_roscore_running():
        print("[INFO] ROS Master already running.")
        return
    print("[INFO] ROS Master not found, starting roscore...")
    subprocess.Popen(["roscore"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(20):
        if is_roscore_running():
            print("[INFO] roscore started successfully.")
            return
        time.sleep(0.5)
    raise RuntimeError("Failed to start roscore.")

def spawn_task(script_path: str, task_id: str, cwd: str = CATKIN_WS):
    """
    启动脚本：
    - 使用 bash -lc 保证是“登录 shell”语义（systemd 下更稳）
    - stdout/stderr 落盘到 LOG_DIR
    """
    ts = time.strftime("%Y%m%d_%H%M%S")
    log_path = str(LOG_DIR / f"{Path(script_path).stem}_{task_id}_{ts}.log")

    # 用 bash -lc 执行，避免 systemd 环境 PATH 等不一致
    cmd = [
        "bash", "-lc",
        f"bash {shlex.quote(script_path)} {shlex.quote(task_id)}"
    ]

    # 关键：不要 PIPE！直接写日志文件（不会卡住，也能看到输出）
    logf = open(log_path, "a", buffering=1)  # 行缓冲
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    p = subprocess.Popen(
        cmd,
        stdout=logf,
        stderr=subprocess.STDOUT,
        cwd=cwd,
        env=env,
        start_new_session=True,   # 进程组隔离，后续好管理/kill
    )

    # 父进程可以关闭句柄；子进程已继承 FD，不影响子进程继续写日志
    try:
        logf.flush()
        logf.close()
    except Exception:
        pass

    return p, log_path


class RobotStateManager:
    HISTORY_LIMIT = 5

    def __init__(self):
        self.active_task: Optional[TaskState] = None
        self.task_history: Dict[str, TaskState] = {}
        self.history_order: Deque[str] = deque()

        self.status_pub = None
        if ROS_AVAILABLE:
            try:
                ensure_roscore()
                rospy.init_node("robot_http_bridge", anonymous=True, disable_signals=True)
                self.status_pub = rospy.Publisher("/robot/api_status", String, queue_size=10)
                rospy.loginfo("RobotStateManager initialized with ROS Publisher.")
            except Exception as e:
                print(f"[WARN] ROS init failed, disable ROS features: {e}")
                self.status_pub = None

    def _push_history(self, task: TaskState):
        tid = task.task_id
        self.task_history[tid] = task
        self.history_order.append(tid)
        while len(self.history_order) > self.HISTORY_LIMIT:
            old = self.history_order.popleft()
            if old in self.task_history:
                del self.task_history[old]

    def update_state(self):
        global_status = TaskStatus.IDLE

        if self.active_task and self.active_task.process:
            ret = self.active_task.process.poll()

            if ret is None:
                self.active_task.status = TaskStatus.EXECUTING
                global_status = TaskStatus.EXECUTING
            else:
                # 子进程结束
                self.active_task.returncode = ret
                self.active_task.end_ts = time.time()
                if ret == 0:
                    self.active_task.status = TaskStatus.SUCCESS
                else:
                    self.active_task.status = TaskStatus.FAILED

                finished = self.active_task
                self.active_task = None
                self._push_history(finished)

        # 发布 ROS 状态（如果可用）
        if ROS_AVAILABLE and self.status_pub and (not rospy.is_shutdown()):
            active_id = self.active_task.task_id if self.active_task else "None"
            msg = f"{global_status.value}:{active_id}"
            try:
                self.status_pub.publish(msg)
            except Exception:
                pass

        return global_status


# -----------------------------
# FastAPI
# -----------------------------
app = FastAPI(
    title="Robot Task Scheduler",
    version="1.0.0",
    description="HTTP-based task scheduling service for ROS robots."
)

state_manager = RobotStateManager()


@app.get("/")
async def root():
    return {"message": "ROS1 Robot API is running.", "ros_available": bool(ROS_AVAILABLE)}


@app.post("/start_task")
async def start_task(task: TaskRequest):
    # 先刷新状态
    state_manager.update_state()

    # 1) 不允许并发任务
    if state_manager.active_task:
        return {
            "status": TaskStatus.EXECUTING,
            "message": f"Rejecting request. Task {state_manager.active_task.task_id} is still executing.",
            "current_task_id": state_manager.active_task.task_id,
            "current_log_path": state_manager.active_task.log_path,
            "pid": state_manager.active_task.process.pid if state_manager.active_task.process else None,
        }

    # 2) 校验任务类型
    if task.task_type not in TASKS:
        raise HTTPException(status_code=400, detail=f"Invalid task type: {task.task_type}")

    script_path = TASKS[task.task_type]
    if not os.path.exists(script_path):
        raise HTTPException(status_code=500, detail=f"Script not found: {script_path}")

    # 3) 启动子进程（关键：落盘日志 + 固定 cwd）
    try:
        proc, log_path = spawn_task(script_path, task.task_id, cwd=CATKIN_WS)
        state_manager.active_task = TaskState(
            process=proc,
            task_type=task.task_type,
            task_id=task.task_id,
            log_path=log_path,
        )

        return {
            "status": TaskStatus.EXECUTING,
            "message": f"Started {task.task_type}",
            "task_id": task.task_id,
            "pid": proc.pid,
            "log_path": log_path,
            "cwd": CATKIN_WS,
        }

    except Exception as e:
        state_manager.active_task = None
        raise HTTPException(status_code=500, detail=f"Failed to start task: {e}")


@app.get("/status")
async def get_status(task_id: Optional[str] = None, log_tail_lines: int = DEFAULT_LOG_TAIL_LINES):
    # 查询时刷新状态
    state_manager.update_state()

    # 1) 查询指定 task_id
    if task_id:
        if state_manager.active_task and state_manager.active_task.task_id == task_id:
            t = state_manager.active_task
            return {
                "task_id": task_id,
                "status": t.status,
                "type": t.task_type,
                "pid": t.process.pid if t.process else None,
                "log_path": t.log_path,
                "returncode": None,
                "log_tail": tail_file(t.log_path, log_tail_lines),
            }

        if task_id in state_manager.task_history:
            t = state_manager.task_history[task_id]
            return {
                "task_id": task_id,
                "status": t.status,
                "type": t.task_type,
                "pid": None,
                "log_path": t.log_path,
                "returncode": t.returncode,
                "duration_s": (t.end_ts - t.start_ts) if (t.end_ts and t.start_ts) else None,
                "log_tail": tail_file(t.log_path, log_tail_lines),
            }

        raise HTTPException(
            status_code=404,
            detail=f"Task ID '{task_id}' not found (history keeps last {state_manager.HISTORY_LIMIT}).",
        )

    # 2) 查询全局状态
    if state_manager.active_task:
        t = state_manager.active_task
        return {
            "global_status": TaskStatus.EXECUTING,
            "active_task_id": t.task_id,
            "pid": t.process.pid if t.process else None,
            "log_path": t.log_path,
            "message": "A task is currently executing.",
            "log_tail": tail_file(t.log_path, log_tail_lines),
        }
    else:
        return {
            "global_status": TaskStatus.IDLE,
            "active_task_id": None,
            "message": "The system is currently idle.",
        }


if __name__ == "__main__":
    print("[INFO] Starting Uvicorn Server on port 8080...")
    uvicorn.run(app, host="0.0.0.0", port=8080)
