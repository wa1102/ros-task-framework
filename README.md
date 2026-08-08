# ROS Task Framework

> A Lightweight HTTP-to-ROS Task Scheduling Framework

ROS Task Framework is a lightweight task scheduling framework designed for ROS1-based robotic systems. It provides a unified RESTful API for external platforms to trigger robot behaviors through HTTP requests.

The framework manages the complete execution pipeline from HTTP task requests to robot execution, including task dispatching, ROS environment initialization, ROS Launch startup, Python task execution, task status monitoring, logging, and resource cleanup.

The framework is designed as a middleware layer between external scheduling platforms and ROS robots, providing a simple and extensible solution for industrial robot task integration.

## Project Structure

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
python ros_server.py
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
    "message": "Task started"
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
    "log_path": "logs/task_001.log"
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
    "global_status": "idle"
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

source ~/catkin_ws/devel/setup.bash

```

Then send an HTTP request to start the task:

```bash
curl -X POST \
http://localhost:8080/start_task \
-H "Content-Type: application/json" \
-d '{
    "task_type":"pick_object",
    "task_id":"001"
}'
```

The framework will automatically execute the task workflow:

```
HTTP Request
      |
      v
FastAPI Server
      |
      v
Task Dispatcher
      |
      v
Shell Script
      |
      v
ROS Launch
      |
      v
Python Robot Task
      |
      v
Logging and Resource Cleanup
```
