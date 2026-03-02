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
| connectors | array | No | - | Connector UUIDs (see [Connectors](#connectors) section) |
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

## Connectors

Connectors let Manus access your third-party apps during task execution. Each connector has a fixed UUID. Pass them in the `connectors` array when creating a task.

**Setup:** Configure connectors at [manus.im](https://manus.im) via OAuth before using them in API calls.

**Docs:** https://open.manus.im/docs/connectors

**Discovery endpoint:** `POST https://api.manus.im/connectors.v1.ConnectorsPublicService/PublicListConnectors` (empty body, returns JSON). See [PublicListConnectors.json](PublicListConnectors.json) for cached response.

### Connector Types

- **builtin** — First-party integrations managed by Manus (My Browser, Gmail, Google Calendar, etc.)
- **mcp** — Third-party integrations via MCP protocol (Slack, Notion, Stripe, etc.)
- **byok** — Bring Your Own Key integrations requiring an external API key (OpenAI, Anthropic, etc.)

### Builtin Connectors

| Connector | UUID |
|-----------|------|
| My Browser | `be268223-40b2-4f3c-a907-c12eb1699283` |
| Gmail | `9444d960-ab7e-450f-9cb9-b9467fb0adda` |
| Google Calendar | `dd5abf31-7ad3-4c0b-9b9a-f0a576645baf` |
| Google Drive | `f8900a57-4bd7-46cc-83a3-5ebd2420a817` |
| GitHub | `bbb0df76-66bd-4a24-ae4f-2aac4750d90b` |
| Instagram | `4b899211-fd12-410e-a8d2-264a409cbc78` |
| Meta Ads Manager | `c073ede4-35a7-4c89-8158-c9b40c489932` |
| Outlook Mail | `d485c6dd-4939-40fb-9c4a-c9821971468b` |
| Outlook Calendar | `4bca3029-d276-4644-898d-578a723361b2` |

### MCP Connectors

| Connector | UUID |
|-----------|------|
| Slack | `001e6a99-5585-4b3e-b8cb-533fe24d7788` |
| Notion | `9c27c684-2f4f-4d33-8fcf-51664ea15c00` |
| Zapier | `433d2fe0-e56d-42b2-8625-9996eab0bb1d` |
| Asana | `219459c8-f04d-41af-9a0d-6f9159bf9205` |
| monday.com | `40ecbda4-5aaf-4e95-bf54-679299ea1c19` |
| Make | `f8405590-5602-4fee-bfd6-f221623e6f72` |
| Linear | `982c169d-0c89-4dbd-95fd-30b49cc2f71e` |
| Atlassian | `74d21d62-2ba7-4840-a918-c8327db5c711` |
| ClickUp | `e08b2bda-a4a6-488a-b397-c72f0923bdf4` |
| Supabase | `84ab78ef-139c-48ff-acd4-cba718b8a484` |
| Vercel | `a50c5d31-af5e-4e01-a992-057663a7ee1f` |
| Neon | `9a0c8590-c0d9-498b-9b3d-bd0df0dbc134` |
| Prisma Postgres | `4c55391d-38ea-4a36-a670-a59a1c7680cb` |
| Sentry | `838d5e1c-7dd4-4782-9429-c459126707c7` |
| Hugging Face | `bdfa81ea-c0ca-4022-bba1-805c48b583c1` |
| HubSpot | `b389f747-6221-41aa-9dbb-732a97a02ea6` |
| Intercom | `73f5f556-978a-4f8a-85b3-ef2eec4473e5` |
| Stripe | `29986b52-7cbb-4d5e-9263-dd0abacaf28d` |
| PayPal for Business | `e90398ef-c17d-46e8-86d6-0bd98642cbbb` |
| RevenueCat | `a104e1ac-73e5-482f-96e6-8b95f4756f27` |
| Close | `9b37aa72-4089-4f25-b774-122860ba61fa` |
| Xero | `7c635638-0b9f-40f4-b5c8-6f2762416d79` |
| Airtable | `d669ca60-22cf-4e16-93d4-845071f9216c` |
| Dify | `888c4ef0-4ed7-4f8b-ade0-55a86fc531dc` |
| Cloudflare | `119e6b13-c2e3-48db-b568-f82191de6b4e` |
| PostHog | `89dac2c3-74d0-4f94-86d1-0ee6c4566193` |
| Playwright | `356d5bc1-fb9f-4fa1-babb-05039dc09d63` |
| Canva | `c63d86db-4c98-483a-af0c-f94721d7f2a5` |
| Webflow | `1d489fb9-0601-4ea7-9942-b866657178c1` |
| Wix | `d0fa4acf-7cf6-4402-bd84-82a850342a79` |
| Granola | `0d21d573-1ee0-484b-8e91-aed6534dbb19` |
| Fireflies | `1b62b634-58e9-4b49-b327-339cc5aaeaf5` |
| tl;dv | `f7bbbff0-61fe-458b-975a-3e2f6a91269c` |
| Firecrawl | `abb9ed36-e693-44ab-be3d-1f5c3bb02294` |
| Todoist | `2900673c-afaa-4dfa-901d-00a6b3f7275e` |
| ZoomInfo | `d1edd2c7-392f-4132-bcf7-7f86efe1db54` |
| Explorium | `3cb9f78b-b53a-49ef-b65e-b56eeddd641d` |
| Serena | `f7f15fe8-15cf-4fb9-a546-720f16dcf5e6` |
| Wrike | `0cac2dee-dc77-43f4-87cc-df68fb723808` |
| HeyGen | `c183add9-c22c-4199-b7f2-d885571afa3a` |
| Invideo | `5db8da88-d801-490d-9094-47d538b484df` |
| LINE | `94c74572-5587-4b9e-8614-2b2cef7413b6` |
| Jotform | `92262486-6778-4451-9921-8c29c9dfa60a` |
| PopHIVE | `63e9fd2a-2804-4509-897a-a9544c127b2b` |
| MiniMax | `1987d07e-eb26-479f-867b-ad4b79c80d11` |
| Jam | `45d392d3-d308-4cdb-8a2d-5d249bcec594` |
| Metabase | `9fe14dac-4288-4371-91a8-86a36051a865` |
| Hume | `a4fc87c3-c8bf-4344-a776-3b42b0546f13` |

### BYOK Connectors (Bring Your Own Key)

| Connector | UUID |
|-----------|------|
| OpenAI | `942ea72c-09f6-46f0-b4b3-f9890a6edbc5` |
| Anthropic | `815b5a30-463e-4662-8da7-081e3b5dfc7d` |
| Google Gemini | `4157dedf-1326-4be8-9295-51416c7dba62` |
| Perplexity | `2a574fdc-89ab-4ad7-b334-e2c156201b6f` |
| Cohere | `bbec86c8-29f6-4149-9bba-d5c66bd6a701` |
| ElevenLabs | `23181678-c628-4c53-9a77-36778a36bbe5` |
| Grok | `491cde51-195c-4e72-96ea-8d80557c3b58` |
| OpenRouter | `c55a74cf-a236-4eda-8885-365d336cae4b` |
| Ahrefs | `305b3b49-32ce-4b2b-a355-3492fe85d17f` |
| Similarweb | `700c656f-b4a4-4e39-a886-a20782d99b6f` |
| Dropbox | `2918a878-d84d-47af-94ce-4967b72506f5` |
| Flux | `5c305236-d14e-43f7-93ff-b288afd26f09` |
| Kling | `99474cab-58bf-47ae-af0e-43c156703be9` |
| Tripo AI | `3db6c7f4-0ce6-4b76-baad-c6e3c4882acd` |
| n8n | `d6b4170a-4001-450d-823a-287dfd9716a7` |
| Stripe API | `fb659ead-d821-40cc-ab35-1cad9af13649` |
| Cloudflare API | `80bca437-287e-4407-adf0-1a0b298528e5` |
| Supabase API | `86a04f98-35cf-4099-9044-ab851a473cf5` |
| Polygon.io | `376008de-cd2a-4bfb-93aa-2652b8585c8e` |
| Mailchimp Marketing | `331ff697-8348-4ed7-a596-7df98740fc1f` |
| Apollo | `bb2a05d0-d728-48eb-b796-9b71e4f9c9ee` |
| JSONBin.io | `c8298c13-6d9a-4847-9f1f-1523952fddbd` |
| Typeform | `658a2969-b74c-42c5-a7b3-9b98128ff724` |
| HeyGen API | `062ba883-f91d-46f2-b1d1-864924865703` |

### Example: Task with My Browser

```bash
curl -X POST https://api.manus.ai/v1/tasks \
  -H "API_KEY: $MANUS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
  "prompt": "Check my recent orders on Amazon",
  "connectors": ["be268223-40b2-4f3c-a907-c12eb1699283"]
}'
```

### Example: Multiple connectors

```bash
curl -X POST https://api.manus.ai/v1/tasks \
  -H "API_KEY: $MANUS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
  "prompt": "What meetings do I have tomorrow? Draft replies to any related emails.",
  "mode": "fast",
  "connectors": [
    "9444d960-ab7e-450f-9cb9-b9467fb0adda",
    "dd5abf31-7ad3-4c0b-9b9a-f0a576645baf"
  ]
}'
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
