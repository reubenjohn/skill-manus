# Manus API Reference

Complete reference for all 13 Manus API endpoints.

**Base URL:** `https://api.manus.ai`
**Auth:** Include `API_KEY: <your-key>` header with every request.
**Docs:** https://open.manus.im/docs

## Authentication

All requests require the `API_KEY` header:

```bash
curl -H "API_KEY: $MANUS_API_KEY" https://api.manus.ai/v1/tasks
```

Get your API key at https://manus.im.

---

## Tasks

### POST /v1/tasks - Create Task

Creates a new task for the Manus agent to process.

**Request Body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| prompt | string | Yes | - | Task instruction for the agent |
| agentProfile | enum | No | manus-1.6 | `manus-1.6`, `manus-1.6-lite`, `manus-1.6-max` |
| taskMode | enum | No | - | `chat`, `adaptive`, `agent` |
| attachments | array | No | - | File/image attachments (file_id, URL, or base64) |
| connectors | array | No | - | Connector IDs (Gmail, Calendar, Notion) |
| hideInTaskList | boolean | No | false | Hide from task list |
| createShareableLink | boolean | No | false | Create public link |
| taskId | string | No | - | Existing task ID for multi-turn conversation |
| locale | string | No | - | Locale code (e.g. `en-US`, `zh-CN`) |
| projectId | string | No | - | Project ID to associate with |
| interactiveMode | boolean | No | false | Allow follow-up questions |

**Response (200):**

```json
{
  "task_id": "task_abc123",
  "task_title": "Write a report",
  "task_url": "https://manus.im/tasks/task_abc123",
  "share_url": "https://manus.im/share/..."
}
```

`share_url` only present when `createShareableLink` is true.

### GET /v1/tasks/{task_id} - Get Task

Retrieve full task details by ID.

**Query Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| convert | boolean | Convert output (currently pptx only) |

**Response (200):**

```json
{
  "id": "task_abc123",
  "object": "task",
  "created_at": 1699900000,
  "updated_at": 1699900100,
  "status": "completed",
  "error": null,
  "incomplete_details": null,
  "instructions": "Write a report",
  "max_output_tokens": null,
  "model": "manus-1.6",
  "metadata": {
    "task_title": "Write a report",
    "task_url": "https://manus.im/tasks/task_abc123"
  },
  "output": [
    {
      "id": "msg_1",
      "status": "completed",
      "role": "user",
      "type": "message",
      "content": [
        {
          "type": "output_text",
          "text": "Here is your report...",
          "fileUrl": "https://...",
          "fileName": "report.pdf",
          "mimeType": "application/pdf"
        }
      ]
    }
  ],
  "locale": "en-US",
  "credit_usage": 5
}
```

**Task statuses:** `pending`, `running`, `completed`, `failed`

### GET /v1/tasks - List Tasks

List tasks with optional filtering and pagination.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| after | string | - | Cursor: last task ID from previous page |
| limit | integer | 100 | Max results (1-1000) |
| order | string | desc | Sort direction: `asc` or `desc` |
| orderBy | string | created_at | Sort field: `created_at` or `updated_at` |
| query | string | - | Search title and body content |
| status | string[] | - | Filter by status (repeatable) |
| createdAfter | integer | - | Unix timestamp |
| createdBefore | integer | - | Unix timestamp |
| project_id | string | - | Filter by project |

**Response (200):**

```json
{
  "object": "list",
  "data": [ ... task objects ... ],
  "first_id": "task_first",
  "last_id": "task_last",
  "has_more": true
}
```

Use `last_id` as `after` parameter for next page.

### PUT /v1/tasks/{task_id} - Update Task

Update task metadata (title, sharing, visibility).

**Request Body:**

| Field | Type | Description |
|-------|------|-------------|
| title | string | New title |
| enableShared | boolean | Enable/disable public sharing |
| enableVisibleInTaskList | boolean | Show/hide in task list |

**Response (200):**

```json
{
  "task_id": "task_abc123",
  "task_title": "Updated title",
  "task_url": "https://...",
  "share_url": "https://..."
}
```

### DELETE /v1/tasks/{task_id} - Delete Task

Permanently delete a task. Cannot be undone.

**Response (200):**

```json
{
  "id": "task_abc123",
  "object": "task.deleted",
  "deleted": true
}
```

---

## Files

### POST /v1/files - Create File

Creates a file record and returns a presigned URL for uploading to S3.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| filename | string | Yes | Name for the file |

**Response (200):**

```json
{
  "id": "file_abc123",
  "object": "file",
  "filename": "report.pdf",
  "status": "pending",
  "upload_url": "https://s3.amazonaws.com/...",
  "upload_expires_at": "2026-02-17T12:00:00Z",
  "created_at": "2026-02-17T11:00:00Z"
}
```

**Upload flow:** After receiving the response, PUT file content to `upload_url`:

```bash
curl -X PUT -H "Content-Type: application/pdf" \
  --data-binary @report.pdf \
  "https://s3.amazonaws.com/..."
```

The file ID can then be used in task attachments.

### GET /v1/files/{file_id} - Get File

Retrieve file details by ID.

**Response (200):**

```json
{
  "id": "file_abc123",
  "object": "file",
  "filename": "report.pdf",
  "status": "uploaded",
  "created_at": "2026-02-17T11:00:00Z"
}
```

**File statuses:** `pending`, `uploaded`, `deleted`

### GET /v1/files - List Files

Retrieve the 10 most recently uploaded files.

**Response (200):**

```json
{
  "object": "list",
  "data": [ ... file objects ... ]
}
```

### DELETE /v1/files/{file_id} - Delete File

Delete file record and S3 object.

**Response (200):**

```json
{
  "id": "file_abc123",
  "object": "file.deleted",
  "deleted": true
}
```

**Response (404):**

```json
{
  "code": 5,
  "message": "file not found or has been deleted",
  "details": []
}
```

---

## Webhooks

### POST /v1/webhooks - Create Webhook

Register a webhook endpoint for real-time task event notifications.

**Important:** Before activation, Manus sends a test POST to verify your endpoint. It must respond with HTTP 200 within 10 seconds.

**Request Body:**

```json
{
  "webhook": {
    "url": "https://example.com/manus-webhook"
  }
}
```

**Response (200):**

```json
{
  "webhook_id": "wh_abc123"
}
```

### DELETE /v1/webhooks/{webhook_id} - Delete Webhook

Remove a webhook configuration.

**Response:** 204 No Content

### Webhook Event Types

Events are delivered as POST requests to your webhook URL.

#### task_created

Sent once when a task is created.

```json
{
  "event_id": "evt_1",
  "event_type": "task_created",
  "task_id": "task_abc123",
  "task_title": "Write a report",
  "task_url": "https://manus.im/tasks/task_abc123"
}
```

#### task_progress

Sent multiple times as the task executes.

```json
{
  "event_id": "evt_2",
  "event_type": "task_progress",
  "task_id": "task_abc123",
  "progress_type": "plan_update",
  "message": "Researching topic..."
}
```

#### task_stopped

Sent when a task completes or needs user input.

```json
{
  "event_id": "evt_3",
  "event_type": "task_stopped",
  "task_id": "task_abc123",
  "task_title": "Write a report",
  "task_url": "https://manus.im/tasks/task_abc123",
  "message": "Report complete",
  "attachments": [
    {
      "file_name": "report.pdf",
      "url": "https://...",
      "size_bytes": 12345
    }
  ],
  "stop_reason": "finish"
}
```

**stop_reason values:**
- `finish` - Task completed
- `ask` - Task needs user input (interactive mode)

---

## Projects

### POST /v1/projects - Create Project

Create a project to organize tasks and apply consistent instructions.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Project name |
| instruction | string | No | Default instruction for all tasks in this project |

**Response (200):**

```json
{
  "id": "proj_abc123",
  "name": "Research Project",
  "instruction": "Start with key findings summary",
  "created_at": 1699900000
}
```

### GET /v1/projects - List Projects

List all projects in your account.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| limit | integer | 100 | Max results (1-1000) |

**Response (200):**

```json
{
  "data": [
    {
      "id": "proj_abc123",
      "name": "Research Project",
      "instruction": "Start with key findings summary",
      "created_at": 1699900000
    }
  ]
}
```

---

## Agent Profiles

| Profile | Description |
|---------|-------------|
| `manus-1.6` | Standard (default) |
| `manus-1.6-lite` | Faster, lighter tasks |
| `manus-1.6-max` | More thorough, complex tasks |

## Task Modes

| Mode | Description |
|------|-------------|
| `chat` | Conversational interaction |
| `adaptive` | Automatically selects best approach |
| `agent` | Full autonomous agent mode |

## Error Responses

Errors return JSON with code and message:

```json
{
  "code": 5,
  "message": "resource not found",
  "details": []
}
```

Common HTTP status codes:
- `400` - Bad request (invalid parameters)
- `401` - Unauthorized (invalid API key)
- `404` - Resource not found
- `429` - Rate limited
- `500` - Server error
