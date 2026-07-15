from pathlib import Path
import yaml

# ---------------------------------
# Project Root
# ---------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------
# Runtime Config
# ---------------------------------

CATKIN_WS = str(BASE_DIR)

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

DEFAULT_LOG_TAIL_LINES = 80

# ---------------------------------
# Task Config
# ---------------------------------

TASK_FILE = BASE_DIR / "config" / "tasks.yaml"

with open(TASK_FILE, "r", encoding="utf-8") as f:
    data = yaml.safe_load(f)

TASKS = {
    name: str(BASE_DIR / info["script"])
    for name, info in data["tasks"].items()
}