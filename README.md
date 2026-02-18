# Manus CLI

Zero-dependency Python CLI for the [Manus AI API](https://open.manus.im/docs). Covers all 13 endpoints.

Built as a [Claude Code skill](https://docs.anthropic.com/en/docs/claude-code) - works standalone or as an integrated tool for AI agents.

## Installation

### ClawHub (Recommended)

```bash
npx clawhub@latest install reubenjohn/skill-manus
```

### Manual (Claude Code skill)

Copy the `manus/` folder into your project's `.claude/skills/` directory:

```bash
git clone https://github.com/reubenjohn/skill-manus.git
cp -r skill-manus/ /path/to/project/.claude/skills/manus/
```

### Standalone

Just grab the single file:

```bash
curl -O https://raw.githubusercontent.com/reubenjohn/skill-manus/main/manus.py
```

## Setup

Get your API key at [manus.im](https://manus.im), then:

```bash
export MANUS_API_KEY="your-api-key"
```

## Usage

```bash
python3 manus.py <resource> <action> [options]
```

### Tasks

```bash
# Create a task
python3 manus.py tasks create --prompt "Write a market analysis report"

# Create and wait for completion
python3 manus.py tasks create --prompt "Analyze this data" --wait --poll-interval 10

# Create with options
python3 manus.py tasks create --prompt "Quick summary" \
  --profile manus-1.6-lite \
  --mode agent \
  --shareable

# Get task details
python3 manus.py tasks get task_abc123

# List tasks with filters
python3 manus.py tasks list --status completed running --limit 10

# Update task
python3 manus.py tasks update task_abc123 --title "Final Report" --shared

# Delete task
python3 manus.py tasks delete task_abc123

# Wait for a running task
python3 manus.py tasks wait task_abc123 --timeout 300
```

### Files

```bash
# Upload a local file (creates record + uploads to S3)
python3 manus.py files upload report.pdf

# Create file record only (returns presigned upload URL)
python3 manus.py files create report.pdf

# Get file details
python3 manus.py files get file_abc123

# List recent files
python3 manus.py files list

# Delete a file
python3 manus.py files delete file_abc123
```

### Webhooks

```bash
# Register a webhook for task events
python3 manus.py webhooks create --url https://example.com/manus-events

# Remove a webhook
python3 manus.py webhooks delete wh_abc123
```

### Projects

```bash
# Create a project with default instructions
python3 manus.py projects create --name "Research" --instruction "Always cite sources"

# List all projects
python3 manus.py projects list
```

## API Coverage

| # | Endpoint | CLI Command | Status |
|---|----------|-------------|--------|
| 1 | POST /v1/tasks | `tasks create` | ✅ |
| 2 | GET /v1/tasks/{id} | `tasks get` | ✅ |
| 3 | GET /v1/tasks | `tasks list` | ✅ |
| 4 | PUT /v1/tasks/{id} | `tasks update` | ✅ |
| 5 | DELETE /v1/tasks/{id} | `tasks delete` | ✅ |
| 6 | POST /v1/files | `files create` | ✅ |
| 7 | GET /v1/files/{id} | `files get` | ✅ |
| 8 | GET /v1/files | `files list` | ✅ |
| 9 | DELETE /v1/files/{id} | `files delete` | ✅ |
| 10 | POST /v1/webhooks | `webhooks create` | ✅ |
| 11 | DELETE /v1/webhooks/{id} | `webhooks delete` | ✅ |
| 12 | POST /v1/projects | `projects create` | ✅ |
| 13 | GET /v1/projects | `projects list` | ✅ |

Plus composite commands: `files upload` (create + S3 PUT), `tasks wait` (poll until done).

## Output Format

All successful output is **JSON to stdout** (machine-parseable by AI agents). Progress messages and errors go to stderr.

```bash
# Pipe JSON output to jq
python3 manus.py tasks list | jq '.data[].status'

# Errors are structured JSON on stderr
python3 manus.py tasks get bad_id 2>&1 | jq .
```

## Running Tests

```bash
cd /path/to/manus
python3 -m unittest tests.test_manus -v
```

## API Documentation

See [docs/api-reference.md](docs/api-reference.md) for complete endpoint documentation including request/response schemas and webhook event types.

## Requirements

- Python 3.7+
- No external dependencies (stdlib only)

## License

MIT
