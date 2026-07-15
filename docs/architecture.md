# Architecture

## Overview

ROS Task Framework is a lightweight scheduling framework for ROS1 robots.

Instead of coupling robot logic with HTTP services, the framework separates task scheduling into multiple independent layers.

---

## Software Architecture

```
HTTP
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
Python Task
```

---

## Execution Pipeline

A task goes through the following lifecycle.

1. Receive HTTP request

2. Parse task type

3. Lookup task configuration

4. Execute shell script

5. Launch ROS

6. Execute robot task

7. Release resources

8. Save logs

---

## Directory Structure

Describe each module.

server/

Task scheduling.

scripts/

Task launcher.

launch/

ROS environment.

robot_demo/

Example robot task.

config/

Task registration.

---

## Design Principles

• Layered Architecture

• Configuration Driven

• Low Coupling

• Easy Extension

• Easy Integration