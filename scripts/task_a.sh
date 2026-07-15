#!/bin/bash

echo "================================================="
echo "[INFO] Starting Task A"
echo "================================================="

source /opt/ros/noetic/setup.bash
source devel/setup.bash

echo "[INFO] Launching robot..."
roslaunch robot_task_demo bringup.launch &
PID_LAUNCH1=$!

sleep 3

echo "[INFO] Launching camera..."
roslaunch robot_task_demo sensors.launch &
PID_LAUNCH2=$!

echo "[INFO] Waiting for initialization..."
sleep 3

echo "[INFO] Running Task A..."
python3 catkin_ws/src/robot_demo/scripts/demo_task.py --task task_a
PY_RET=$?

echo "[INFO] Task A finished."

echo "[INFO] Cleaning up..."

kill -SIGINT $PID_LAUNCH1 2>/dev/null
kill -SIGINT $PID_LAUNCH2 2>/dev/null

wait $PID_LAUNCH1 2>/dev/null
wait $PID_LAUNCH2 2>/dev/null

echo "[INFO] Task Finished."

exit $PY_RET