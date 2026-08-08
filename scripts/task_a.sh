#!/bin/bash
# ============================================================================
# task_a.sh — Task A: bringup + sensors + demo_task(task_a)
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

echo "================================================="
echo "[INFO] Starting Task A"
echo "================================================="

source_ros_env
launch_ros_core "sensors.launch"
run_python_task "task_a" "${1:-}"
RET=$?
cleanup

echo "[INFO] Task A finished."
exit ${RET}
