"""
Application configuration loaded from the filesystem.

All paths are resolved relative to the project root (the directory that
contains this ``server/`` package).
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Runtime paths
# ---------------------------------------------------------------------------

CATKIN_WS = str(BASE_DIR)

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_LOG_TAIL_LINES: int = 80
MAX_TASK_HISTORY: int = 5
SERVER_HOST: str = "0.0.0.0"
SERVER_PORT: int = 8080

# ---------------------------------------------------------------------------
# Load task registry
# ---------------------------------------------------------------------------

TASK_FILE = BASE_DIR / "config" / "tasks.yaml"

if not TASK_FILE.exists():
    msg = f"Task configuration file not found: {TASK_FILE}"
    raise FileNotFoundError(msg)

with open(TASK_FILE, "r", encoding="utf-8") as fh:
    _raw = yaml.safe_load(fh)

if not _raw or "tasks" not in _raw:
    msg = f"Invalid format in {TASK_FILE}: expected top-level 'tasks' key."
    raise ValueError(msg)

TASKS: dict[str, str] = {}

for _name, _info in (_raw["tasks"] or {}).items():
    if not isinstance(_info, dict) or "script" not in _info:
        logger.warning("Task '%s' is missing a 'script' field — skipping.", _name)
        continue
    _script_path = BASE_DIR / _info["script"]
    if not _script_path.exists():
        logger.warning(
            "Script for task '%s' not found at %s — it will fail at runtime.",
            _name,
            _script_path,
        )
    TASKS[_name] = str(_script_path)

logger.info("Loaded %d task(s) from %s: %s", len(TASKS), TASK_FILE, list(TASKS.keys()))
