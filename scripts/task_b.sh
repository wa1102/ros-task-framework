#!/bin/bash
# ============================================================================
# task_b.sh — Task B: bringup + sensors + demo_task(task_b)
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

echo "================================================="
echo "[INFO] Starting Task B"
echo "================================================="

source_ros_env
launch_ros_core "sensors.launch"
run_python_task "task_b" "${1:-}"
RET=$?
cleanup

echo "[INFO] Task B finished."
exit ${RET}
