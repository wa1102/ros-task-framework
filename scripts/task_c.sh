#!/bin/bash
# ============================================================================
# task_c.sh — Task C: bringup + task.launch (dual camera + TF frames) + demo_task(task_c)
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

echo "================================================="
echo "[INFO] Starting Task C"
echo "================================================="

source_ros_env
launch_ros_core "task.launch"
run_python_task "task_c" "${1:-}"
RET=$?
cleanup

echo "[INFO] Task C finished."
exit ${RET}
