---
name: manus
description: CLI client for the Manus AI API. Create and manage AI agent tasks, upload files, configure webhooks, and manage projects. Requires MANUS_API_KEY env var.
user-invokable: true
---

# Manus AI CLI

Zero-dependency Python CLI for all 13 Manus API endpoints.

## When to Use

- Create an AI agent task: `python3 manus.py tasks create --prompt "..."`
- Upload files for task analysis
- Set up webhooks for real-time task notifications
- Manage projects for organizing related tasks
- Poll/wait for task completion

## Prerequisites

```bash
export MANUS_API_KEY="your-key"  # Get at https://manus.im
```

## Quick Reference

| Command | Description |
|---------|-------------|
| `tasks create --prompt "..."` | Create a new task |
| `tasks create --prompt "..." --wait` | Create and wait for completion |
| `tasks get <id>` | Get task details |
| `tasks list` | List tasks (with filters) |
| `tasks update <id> --title "..."` | Update task metadata |
| `tasks delete <id>` | Delete a task |
| `tasks wait <id>` | Poll until done |
| `files upload <path>` | Upload a local file |
| `files create <name>` | Get presigned upload URL |
| `files get <id>` | Get file details |
| `files list` | List recent files |
| `files delete <id>` | Delete a file |
| `webhooks create --url <url>` | Register webhook |
| `webhooks delete <id>` | Remove webhook |
| `projects create --name "..."` | Create project |
| `projects list` | List projects |

All commands output JSON to stdout. Progress and errors go to stderr.

## Common Workflows

### Create task and wait for result

```bash
python3 manus.py tasks create --prompt "Research AI trends in 2026" --wait
```

### Upload file and attach to task

```bash
# Upload file (returns file ID)
python3 manus.py files upload report.pdf

# Create task with attachment
python3 manus.py tasks create --prompt "Summarize this document" --attachment file_abc123
```

### Set up webhook for notifications

```bash
python3 manus.py webhooks create --url https://example.com/manus-events
```

### Use a project for consistent instructions

```bash
# Create project
python3 manus.py projects create --name "Research" --instruction "Always cite sources"

# Create task in project
python3 manus.py tasks create --prompt "Find papers on X" --project-id proj_abc123
```

## Connectors

Pass connector UUIDs to give Manus access to the user's apps. Must be pre-configured via OAuth at manus.im.

**Common connectors:**

| Connector | UUID | Type |
|-----------|------|------|
| My Browser | `be268223-40b2-4f3c-a907-c12eb1699283` | builtin |
| Gmail | `9444d960-ab7e-450f-9cb9-b9467fb0adda` | builtin |
| Google Calendar | `dd5abf31-7ad3-4c0b-9b9a-f0a576645baf` | builtin |
| Google Drive | `f8900a57-4bd7-46cc-83a3-5ebd2420a817` | builtin |
| GitHub | `bbb0df76-66bd-4a24-ae4f-2aac4750d90b` | builtin |
| Notion | `9c27c684-2f4f-4d33-8fcf-51664ea15c00` | mcp |
| Slack | `001e6a99-5585-4b3e-b8cb-533fe24d7788` | mcp |

Full list (70+ connectors): [api-reference.md](docs/api-reference.md) or [PublicListConnectors.json](docs/PublicListConnectors.json)

Discovery endpoint: `POST https://api.manus.im/connectors.v1.ConnectorsPublicService/PublicListConnectors`

```bash
# Task using My Browser (for authenticated web access)
python3 manus.py tasks create --prompt "Check my recent emails" --connector 9444d960-ab7e-450f-9cb9-b9467fb0adda
```

## Error Handling

Errors are structured JSON on stderr:

```json
{
  "error": true,
  "message": "GET /v1/tasks/bad_id returned 404: Task not found",
  "status_code": 404,
  "method": "GET",
  "path": "/v1/tasks/bad_id"
}
```

## API Docs

See [docs/api-reference.md](docs/api-reference.md) for complete API documentation.
