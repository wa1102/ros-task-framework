# REST API

## POST /start_task

Start a robot task.

### Request

```json
{
    "task_type":"button",
    "task_id":"001"
}
```

### Response

```json
{
    "status":"executing",
    "task_id":"001"
}
```

---

## GET /status

Query task status.

### Example

```text
GET /status?task_id=001
```

Response

```json
{
    "status":"success"
}
```

---

## GET /

Health check.

Response

```json
{
    "message":"ROS Task Framework Running"
}
```