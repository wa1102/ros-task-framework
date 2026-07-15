# Add a New Task

Adding a new robot task only requires three steps.

---

## Step 1

Create a shell script.

Example

scripts/task_pick.sh

---

## Step 2

Register the task.

tasks.yaml

```yaml
pick:
  script: scripts/task_pick.sh
```

---

## Step 3

Send HTTP request.

```json
{
    "task_type":"pick",
    "task_id":"001"
}
```

The framework automatically dispatches the task.

No modification of ros_server.py is required.