# ROS Task Framework

> A Lightweight HTTP-to-ROS Task Scheduling Framework

ROS Task Framework is a lightweight task scheduling framework designed for ROS1-based robotic systems. It provides a complete execution pipeline from HTTP requests to robot task execution, enabling third-party platforms to trigger robot behaviors through a unified RESTful API.

The framework integrates FastAPI, Shell scripting, ROS Launch, and Python task execution into a modular architecture, making it easy to deploy, extend, and integrate into industrial robotic applications.

---

## ✨ Features

- 🚀 HTTP-based robot task scheduling using FastAPI
- 🤖 Automatic ROS Launch startup and shutdown
- 📋 Unified task lifecycle management
- 📄 Real-time task status and log monitoring
- 🧹 Automatic resource cleanup after task execution
- 🔧 Easy integration with third-party scheduling platforms

---

# Architecture

The framework follows a layered task execution pipeline.

```text
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

# Project Structure

```text
ros-task-framework/

├── server/
│   ├── ros_server.py          # FastAPI task scheduler
│   ├── settings.py            # Runtime configuration
│   └── __init__.py
│
├── config/
│   └── tasks.yaml             # Task registration
│
├── scripts/
│   ├── common.sh              # Shared shell utilities
│   ├── task_a.sh
│   ├── task_b.sh
│   └── task_c.sh
│
├── catkin_ws/
│   └── src/
│       └── robot_demo/
│           ├── launch/
│           │   ├── bringup.launch
│           │   ├── sensors.launch
│           │   └── task.launch
│           │
│           └── scripts/
│               └── demo_task.py
│
├── docs/
├── examples/
└── README.md
```

---

# Task Flow

Every robot task follows the same execution pipeline.

```text
HTTP POST

        │

        ▼

FastAPI receives request

        │

        ▼

Parse task_type

        │

        ▼

Load shell script from tasks.yaml

        │

        ▼

Execute Shell Script

        │

        ▼

Start ROS Launch

        │

        ▼

Run Python Task

        │

        ▼

Cleanup Resources

        │

        ▼

Task Finished
```

The scheduler is responsible for managing the complete task lifecycle, including task dispatching, ROS environment startup, execution monitoring, logging, and resource cleanup.

---

# Quick Start

## 1. Clone the repository

```bash
git clone https://github.com/wa1102/ros-task-framework.git
```

## 2. Install dependencies

```bash
pip install -r requirements.txt
```

## 3. Build Catkin Workspace

```bash
cd catkin_ws

catkin_make

source devel/setup.bash
```

## 4. Start the Task Server

```bash
python ros_server.py
```

The server will start listening on:

```text
http://localhost:8080
```

---
# Task Configuration

Robot tasks are registered through a YAML configuration file rather than hardcoded in the server. This design allows new tasks to be added without modifying the scheduler.

Example:

```yaml
task_a:
  script: scripts/task_a.sh

task_b:
  script: scripts/task_b.sh

task_c:
  script: scripts/task_c.sh
```

The server loads this configuration at startup and dynamically maps `task_type` to the corresponding Shell script.

---

# HTTP API

## Start Task

**POST**

```text
POST /start_task
```

Request

```json
{
    "task_type": "task_a",
    "task_id": "001"
}
```

Response

```json
{
    "status": "executing",
    "task_id": "001",
    "message": "Task started."
}
```

---

## Query Task Status

**GET**

```text
GET /status?task_id=001
```

Example Response

```json
{
    "task_id": "001",
    "status": "executing",
    "log_path": "logs/task_001.log"
}
```

---

## System Status

**GET**

```text
GET /status
```

Example Response

```json
{
    "global_status": "idle"
}
```

---

# Design Highlights

## Layered Task Scheduling Architecture

Instead of directly invoking ROS nodes from the HTTP server, the framework separates responsibilities into five independent layers:

```text
HTTP
    ↓
FastAPI
    ↓
Shell
    ↓
ROS Launch
    ↓
Python Task
```

This layered architecture improves modularity, maintainability, and makes individual task implementations independent of the scheduling framework.

---

## Dynamic Task Registration

Robot tasks are configured through `tasks.yaml`.

Adding a new robot behavior only requires:

1. Writing a Shell script
2. Registering it in `tasks.yaml`

No modifications to the server source code are required.

---

## Unified Task Lifecycle Management

Every task follows the same execution lifecycle:

```text
Receive Request
      ↓
Launch ROS Environment
      ↓
Execute Task
      ↓
Monitor Process
      ↓
Collect Logs
      ↓
Release Resources
```

The scheduler guarantees that ROS resources are properly released after each task, preventing resource conflicts during continuous execution.

---

## Automatic ROS Environment Management

The framework automatically detects whether ROS Master is running before executing a task.

If no ROS Master exists, it launches one automatically before starting robot applications.

This mechanism enables unattended deployment and improves system robustness.

---

## Built-in Logging and Status Monitoring

Each task automatically generates an independent log file.

The server continuously tracks:

- Task status
- Process ID
- Return code
- Execution duration
- Runtime logs

making debugging and system maintenance straightforward.

---

# Repository Overview

This repository focuses on the **task scheduling framework** rather than specific robot algorithms.

The robot-side implementation has been simplified into demonstration tasks while preserving the complete scheduling architecture, including:

- HTTP Task Server
- Task Dispatcher
- Shell Execution Layer
- ROS Launch Management
- Task Registration
- Logging System
- Status Monitoring

The project can serve as a lightweight template for integrating ROS applications with external scheduling platforms.