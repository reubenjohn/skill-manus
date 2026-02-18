---
name: manus
description: CLI client for the Manus AI API. Create and manage AI agent tasks, upload files, configure webhooks, and manage projects. Requires MANUS_API_KEY env var.
user-invocable: true
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
