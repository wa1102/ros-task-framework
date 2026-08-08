# ROS Task Framework

> A Lightweight HTTP-to-ROS Task Scheduling Framework

ROS Task Framework is a lightweight task scheduling framework designed for ROS1-based robotic systems. It provides a unified RESTful API for external platforms to trigger robot behaviors through HTTP requests.

The framework manages the complete execution pipeline from HTTP task requests to robot execution, including task dispatching, ROS environment initialization, ROS Launch startup, Python task execution, task status monitoring, logging, and resource cleanup.

The framework is designed as a middleware layer between external scheduling platforms and ROS robots, providing a simple and extensible solution for industrial robot task integration.

## Video

https://github.com/user-attachments/assets/cbcd96b4-65ba-42c5-8879-c40e1ec7eb1b

A Robot Task Example

https://github.com/user-attachments/assets/cb21d1e8-a45b-4ec5-8a98-5fe73b3a9360

The full implementation of ROS Task Framework

## Project Structure

```
                HTTP Request
                      │
                      ▼
             +----------------+
             | FastAPI Server |
             +----------------+
                      │
                      ▼
             Task Dispatcher
                      │
                      ▼
             Execute Shell Script
                      │
                      ▼
              ROS Launch Files
                      │
                      ▼
             Python Task Script
                      │
                      ▼
             Cleanup & Logging
```

Each task is executed through the same scheduling process, providing a consistent and extensible execution framework.

---

## Quick Start

Clone the repository:

```bash
git clone https://github.com/wa1102/ros-task-framework.git

cd ros-task-framework
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Build ROS workspace:

```bash
cd catkin_ws

catkin_make

source devel/setup.bash
```

Start the task server:

```bash
python server/ros_server.py
```

The server will start at:

```
http://localhost:8080
```

## HTTP API

### Start Task

Request:

```
POST /start_task
```

Example:

```json
{
    "task_type": "task_a",
    "task_id": "001"
}
```

Response:

```json
{
    "status": "executing",
    "task_id": "001",
    "message": "Started task_a",
    "pid": 12345,
    "log_path": "logs/task_a_001_20250101_120000.log"
}
```

### Query Task Status

Request:

```
GET /status?task_id=001
```

Example response:

```json
{
    "task_id": "001",
    "status": "executing",
    "type": "task_a",
    "pid": 12345,
    "log_path": "logs/task_a_001_20250101_120000.log",
    "returncode": null,
    "log_tail": ["[INFO] Executing step 1/5", "..."]
}
```

### Query System Status

Request:

```
GET /status
```

Example response:

```json
{
    "global_status": "idle",
    "active_task_id": null,
    "message": "System is idle."
}
```

## Example

A new robot task can be added without modifying the task scheduler.

First, register the task in:

```
config/tasks.yaml
```

Example:

```yaml
tasks:

  pick_object:
    script: scripts/pick_object.sh
```

Create the corresponding execution script:

```
scripts/pick_object.sh
```

Example:

```bash
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

echo "[INFO] Starting Pick Object Task"

source_ros_env
launch_ros_core "sensors.launch"
python3 catkin_ws/src/robot_demo/scripts/demo_task.py --task pick_object "${1:-}"
RET=$?
cleanup

echo "[INFO] Pick Object Task finished."
exit ${RET}
```

Then send an HTTP request to start the task:

```bash
curl -X POST \
  http://localhost:8080/start_task \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "pick_object",
    "task_id": "001"
  }'
```

The framework will automatically execute the task workflow:

```
HTTP Request
      │
      ▼
FastAPI Server
      │
      ▼
Task Dispatcher
      │
      ▼
Shell Script
      │
      ▼
ROS Launch
      │
      ▼
Python Robot Task
      │
      ▼
Logging and Resource Cleanup
```
