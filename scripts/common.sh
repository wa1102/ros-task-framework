#!/bin/bash
# ============================================================================
# common.sh — Shared helpers sourced by every task script.
#
# Usage (inside a task script):
#
#     SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#     source "${SCRIPT_DIR}/common.sh"
#
#     launch_ros_core                          # start bringup + sensors
#     run_python_task "task_a" "$1"            # run demo_task.py
#     cleanup                                  # kill ROS launchers
# ============================================================================

set -euo pipefail

# --- editable paths ---------------------------------------------------------
ROS_SETUP="/opt/ros/noetic/setup.bash"
CATKIN_SETUP="devel/setup.bash"
BRINGUP_PKG="robot_task_demo"
DEMO_SCRIPT="catkin_ws/src/robot_demo/scripts/demo_task.py"

# --- internal state ---------------------------------------------------------
declare -a LAUNCH_PIDS=()

# ---------------------------------------------------------------------------
# source_ros_env — source ROS + catkin workspace setup files
# ---------------------------------------------------------------------------
source_ros_env() {
    echo "[INFO] Sourcing ROS environment …"
    if [[ -f "${ROS_SETUP}" ]]; then
        source "${ROS_SETUP}"
    else
        echo "[WARN] ROS setup not found at ${ROS_SETUP}"
    fi
    if [[ -f "${CATKIN_SETUP}" ]]; then
        source "${CATKIN_SETUP}"
    else
        echo "[WARN] Catkin setup not found at ${CATKIN_SETUP}"
    fi
}

# ---------------------------------------------------------------------------
# launch_ros_core — launch bringup + an optional second launch file
#
# Arguments:
#   $1 — second launch file name (e.g. "sensors.launch" or "task.launch")
#        Defaults to "sensors.launch".
# ---------------------------------------------------------------------------
launch_ros_core() {
    local second_launch="${1:-sensors.launch}"

    echo "[INFO] Launching robot bringup …"
    roslaunch "${BRINGUP_PKG}" bringup.launch &
    LAUNCH_PIDS+=($!)
    sleep 3

    echo "[INFO] Launching ${second_launch} …"
    roslaunch "${BRINGUP_PKG}" "${second_launch}" &
    LAUNCH_PIDS+=($!)
    sleep 3

    echo "[INFO] ROS core is ready."
}

# ---------------------------------------------------------------------------
# run_python_task — execute the demo Python script
#
# Arguments:
#   $1 — task name passed to --task (e.g. "task_a")
#   $2 — task_id  (from the HTTP request)
# ---------------------------------------------------------------------------
run_python_task() {
    local task_name="${1:?missing task name}"
    local task_id="${2:?missing task id}"

    echo "[INFO] Running ${task_name} (task_id=${task_id}) …"
    python3 "${DEMO_SCRIPT}" --task "${task_name}"
    local ret=$?
    echo "[INFO] ${task_name} finished with exit code ${ret}."
    return ${ret}
}

# ---------------------------------------------------------------------------
# cleanup — send SIGINT to every launched ROS process, then wait
# ---------------------------------------------------------------------------
cleanup() {
    echo "[INFO] Cleaning up launched ROS processes …"
    for pid in "${LAUNCH_PIDS[@]}"; do
        kill -SIGINT "${pid}" 2>/dev/null || true
    done
    for pid in "${LAUNCH_PIDS[@]}"; do
        wait "${pid}" 2>/dev/null || true
    done
    echo "[INFO] Cleanup complete."
}
