#!/usr/bin/env python3
"""
Manus AI API CLI - Zero-dependency Python client for all Manus API endpoints.

Usage:
    python3 manus.py <resource> <action> [options]
    MANUS_API_KEY=<key> python3 manus.py tasks create --prompt "Write a report"

Covers all 13 Manus API endpoints: tasks (CRUD + wait), files (CRUD + upload),
webhooks (create/delete), and projects (create/list).

Environment:
    MANUS_API_KEY   Required. Get yours at https://manus.im
"""

from __future__ import annotations

import argparse
import functools
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL: str = "https://api.manus.ai"
AGENT_PROFILES: List[str] = ["manus-1.6", "manus-1.6-lite", "manus-1.6-max"]
TASK_MODES: List[str] = ["chat", "adaptive", "agent"]
TASK_STATUSES: List[str] = ["pending", "running", "completed", "failed"]
DEFAULT_POLL_INTERVAL: int = 5
DEFAULT_POLL_TIMEOUT: int = 600

# Type alias for JSON-like dicts returned by the API
JsonDict = Dict[str, Any]

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ManusError(Exception):
    """Base error for all Manus CLI errors."""

    def to_dict(self) -> JsonDict:
        return {"error": True, "message": str(self)}


@dataclass
class ManusAPIError(ManusError):
    """HTTP error from the Manus API."""

    message: str
    status_code: int = 0
    method: str = ""
    path: str = ""
    body: Optional[JsonDict] = None

    def __str__(self) -> str:
        return self.message

    def to_dict(self) -> JsonDict:
        d: JsonDict = {
            "error": True,
            "message": self.message,
            "status_code": self.status_code,
            "method": self.method,
            "path": self.path,
        }
        if self.body:
            d["details"] = self.body
        return d


class ManusConfigError(ManusError):
    """Configuration error (missing API key, file not found, etc.)."""


# ---------------------------------------------------------------------------
# HTTP Client
# ---------------------------------------------------------------------------


class ManusClient:
    """Low-level HTTP client for the Manus API. Uses urllib (stdlib only)."""

    def __init__(self, api_key: str, base_url: str = BASE_URL) -> None:
        self.api_key: str = api_key
        self.base_url: str = base_url.rstrip("/")

    def request(
        self,
        method: str,
        path: str,
        *,
        body: Optional[JsonDict] = None,
        query: Optional[JsonDict] = None,
    ) -> Optional[JsonDict]:
        """Make an API request. Returns parsed JSON or None (for 204)."""
        url: str = self.base_url + path
        if query:
            filtered = {k: v for k, v in query.items() if v is not None}
            if filtered:
                url += "?" + urllib.parse.urlencode(filtered, doseq=True)

        data: Optional[bytes] = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("API_KEY", self.api_key)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req) as resp:
                if resp.status == 204:
                    return None
                raw: str = resp.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            err_body: Optional[JsonDict] = None
            try:
                err_body = json.loads(e.read().decode("utf-8"))
            except Exception:
                pass
            msg = f"{method} {path} returned {e.code}"
            if err_body:
                detail = err_body.get("message") or err_body.get("error", {}).get("message", "")
                if detail:
                    msg += f": {detail}"
            raise ManusAPIError(
                msg, status_code=e.code, method=method, path=path, body=err_body
            ) from None
        except urllib.error.URLError as e:
            raise ManusAPIError(
                f"Connection failed for {method} {path}: {e.reason}",
                method=method,
                path=path,
            ) from None


# ---------------------------------------------------------------------------
# High-Level API
# ---------------------------------------------------------------------------


def endpoint(
    http_method: str,
    path_template: str,
    *,
    send: str = "",
) -> Callable:
    """Decorator for ManusAPI methods. Reduces endpoint boilerplate.

    - Path ``{placeholders}`` are filled from positional args or kwargs.
    - The decorated function's return value is used as body/query (when *send* is set).
    - *send*: ``"body"`` | ``"query"`` | ``""`` (no params).
    """
    _placeholders: List[str] = re.findall(r"\{(\w+)\}", path_template)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self: ManusAPI, *args: Any, **kwargs: Any) -> Optional[JsonDict]:
            # Resolve path: positional args fill {placeholders}, then kwargs
            path_vars: Dict[str, Any] = {}
            for i, name in enumerate(_placeholders):
                if i < len(args):
                    path_vars[name] = args[i]
                elif name in kwargs:
                    path_vars[name] = kwargs.pop(name)
            resolved: str = path_template.format(**path_vars)

            if send:
                params = func(self, *args, **kwargs)
            else:
                params = None

            if send == "body":
                return self.client.request(http_method, resolved, body=params)
            elif send == "query":
                return self.client.request(http_method, resolved, query=params)
            return self.client.request(http_method, resolved)

        return wrapper

    return decorator


class ManusAPI:
    """High-level API covering all 13 Manus endpoints + composite operations."""

    def __init__(self, client: ManusClient) -> None:
        self.client: ManusClient = client

    # --- Tasks ---

    @endpoint("POST", "/v1/tasks", send="body")
    def create_task(
        self,
        prompt: str,
        agentProfile: Optional[str] = None,
        taskMode: Optional[str] = None,
        attachments: Optional[List[str]] = None,
        connectors: Optional[List[str]] = None,
        hideInTaskList: bool = False,
        createShareableLink: bool = False,
        taskId: Optional[str] = None,
        locale: Optional[str] = None,
        projectId: Optional[str] = None,
        interactiveMode: bool = False,
    ) -> JsonDict:
        """POST /v1/tasks - Create a new task."""
        params: JsonDict = {"prompt": prompt}
        for k, v in locals().items():
            if k not in ("self", "prompt", "params") and v is not None and v is not False:
                params[k] = v
        if "attachments" in params:
            params["attachments"] = [
                {"type": "file_id", "file_id": fid} for fid in params["attachments"]
            ]
        return params

    @endpoint("GET", "/v1/tasks/{task_id}", send="query")
    def get_task(self, task_id: str, convert: bool = False) -> Optional[JsonDict]:
        """GET /v1/tasks/{task_id} - Get task details."""
        return {"convert": "true"} if convert else None

    @endpoint("GET", "/v1/tasks", send="query")
    def list_tasks(
        self,
        after: Optional[str] = None,
        limit: Optional[int] = None,
        order: Optional[str] = None,
        orderBy: Optional[str] = None,
        query: Optional[str] = None,
        status: Optional[List[str]] = None,
        createdAfter: Optional[str] = None,
        createdBefore: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Optional[JsonDict]:
        """GET /v1/tasks - List tasks with filtering and pagination."""
        params = {k: v for k, v in locals().items() if k != "self" and v is not None}
        return params or None

    @endpoint("PUT", "/v1/tasks/{task_id}", send="body")
    def update_task(
        self,
        task_id: str,
        title: Optional[str] = None,
        enableShared: Optional[bool] = None,
        enableVisibleInTaskList: Optional[bool] = None,
    ) -> Optional[JsonDict]:
        """PUT /v1/tasks/{task_id} - Update task metadata."""
        params = {k: v for k, v in locals().items() if k not in ("self", "task_id") and v is not None}
        return params or None

    @endpoint("DELETE", "/v1/tasks/{task_id}")
    def delete_task(self, task_id: str) -> Optional[JsonDict]:
        """DELETE /v1/tasks/{task_id} - Permanently delete a task."""

    def wait_for_task(
        self,
        task_id: str,
        interval: int = DEFAULT_POLL_INTERVAL,
        timeout: int = DEFAULT_POLL_TIMEOUT,
    ) -> JsonDict:
        """Poll GET /v1/tasks/{task_id} until status is completed or failed."""
        start: float = time.time()
        while True:
            elapsed: int = int(time.time() - start)
            task: JsonDict = self.get_task(task_id)
            status: str = task.get("status", "unknown")
            _progress(f"Status: {status} ({elapsed}s elapsed)")

            if status in ("completed", "failed"):
                return task

            if elapsed >= timeout:
                raise ManusAPIError(
                    f"Timeout after {timeout}s waiting for task {task_id} (last status: {status})",
                    method="GET",
                    path=f"/v1/tasks/{task_id}",
                )
            time.sleep(interval)

    # --- Files ---

    @endpoint("POST", "/v1/files", send="body")
    def create_file(self, filename: str) -> JsonDict:
        """POST /v1/files - Create file record and get presigned upload URL."""
        return {"filename": filename}

    def upload_file_content(self, upload_url: str, file_path: str) -> int:
        """PUT file content to a presigned S3 URL. No auth header needed."""
        path = Path(file_path)
        if not path.exists():
            raise ManusConfigError(f"File not found: {file_path}")

        content_type: str = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        data: bytes = path.read_bytes()

        req = urllib.request.Request(upload_url, data=data, method="PUT")
        req.add_header("Content-Type", content_type)

        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status
        except urllib.error.HTTPError as e:
            raise ManusAPIError(
                f"File upload failed with status {e.code}",
                status_code=e.code,
                method="PUT",
                path="<presigned-url>",
            ) from None

    def upload_file(self, file_path: str) -> JsonDict:
        """Convenience: create file record + upload content in one step."""
        path = Path(file_path)
        if not path.exists():
            raise ManusConfigError(f"File not found: {file_path}")

        record: JsonDict = self.create_file(path.name)
        _progress(f"Uploading {path.name} to presigned URL...")
        self.upload_file_content(record["upload_url"], file_path)
        _progress("Upload complete.")
        return record

    @endpoint("GET", "/v1/files/{file_id}")
    def get_file(self, file_id: str) -> Optional[JsonDict]:
        """GET /v1/files/{file_id} - Get file details."""

    @endpoint("GET", "/v1/files")
    def list_files(self) -> Optional[JsonDict]:
        """GET /v1/files - List 10 most recent files."""

    @endpoint("DELETE", "/v1/files/{file_id}")
    def delete_file(self, file_id: str) -> Optional[JsonDict]:
        """DELETE /v1/files/{file_id} - Delete file record and S3 object."""

    # --- Webhooks ---

    @endpoint("POST", "/v1/webhooks", send="body")
    def create_webhook(self, url: str) -> JsonDict:
        """POST /v1/webhooks - Register a webhook endpoint."""
        return {"webhook": {"url": url}}

    @endpoint("DELETE", "/v1/webhooks/{webhook_id}")
    def delete_webhook(self, webhook_id: str) -> Optional[JsonDict]:
        """DELETE /v1/webhooks/{webhook_id} - Remove a webhook."""

    # --- Projects ---

    @endpoint("POST", "/v1/projects", send="body")
    def create_project(self, name: str, instruction: Optional[str] = None) -> Optional[JsonDict]:
        """POST /v1/projects - Create a project for organizing tasks."""
        body: JsonDict = {"name": name}
        if instruction:
            body["instruction"] = instruction
        return body

    @endpoint("GET", "/v1/projects", send="query")
    def list_projects(self, limit: Optional[int] = None) -> Optional[JsonDict]:
        """GET /v1/projects - List all projects."""
        return {"limit": limit} if limit else None


# ---------------------------------------------------------------------------
# CLI Definition (data-driven)
# ---------------------------------------------------------------------------


@dataclass
class Arg:
    """CLI argument spec. Maps to argparse.add_argument() + API key mapping."""

    name: str                              # CLI flag ("--prompt") or positional ("task_id")
    key: Optional[str] = None              # Python kwarg name if different from CLI dest
    kwargs: Dict[str, Any] = field(default_factory=dict)  # argparse.add_argument() kwargs

    def __init__(self, name: str, *, key: Optional[str] = None, **kwargs: Any) -> None:
        self.name = name
        self.key = key
        self.kwargs = kwargs


# Structure: resource -> (help, {action -> (api_method, help, [Arg, ...])})
CommandAction = tuple  # (method_name: str, help: str, args: List[Arg])
CommandResource = tuple  # (help: str, actions: Dict[str, CommandAction])

COMMANDS: Dict[str, CommandResource] = {
    "tasks": ("Manage tasks", {
        "create": ("create_task", "Create a new task", [
            Arg("--prompt", required=True, help="task instruction for the agent"),
            Arg("--profile", key="agentProfile", default="manus-1.6",
                choices=AGENT_PROFILES, help="agent profile (default: manus-1.6)"),
            Arg("--mode", key="taskMode", choices=TASK_MODES, help="execution mode"),
            Arg("--attachment", key="attachments", action="append",
                help="file ID to attach (repeatable)"),
            Arg("--connector", key="connectors", action="append",
                help="connector ID (repeatable)"),
            Arg("--hide", key="hideInTaskList", action="store_true",
                help="hide from task list"),
            Arg("--shareable", key="createShareableLink", action="store_true",
                help="create a public shareable link"),
            Arg("--continue-task", key="taskId",
                help="existing task ID for multi-turn conversation"),
            Arg("--locale", help="locale code (e.g. en-US, zh-CN)"),
            Arg("--project-id", key="projectId", help="project ID to associate with"),
            Arg("--interactive", key="interactiveMode", action="store_true",
                help="allow Manus to ask follow-up questions"),
        ]),
        "get": ("get_task", "Get task details", [
            Arg("task_id", help="task ID"),
            Arg("--convert", action="store_true",
                help="convert output (currently pptx only)"),
        ]),
        "list": ("list_tasks", "List tasks with optional filtering", [
            Arg("--after", help="cursor: last task ID from previous page"),
            Arg("--limit", type=int, help="max results (1-1000, default: 100)"),
            Arg("--order", choices=["asc", "desc"], help="sort direction"),
            Arg("--order-by", key="orderBy", choices=["created_at", "updated_at"],
                help="sort field"),
            Arg("--query", help="search title and body content"),
            Arg("--status", nargs="+", choices=TASK_STATUSES,
                help="filter by status (space-separated)"),
            Arg("--created-after", key="createdAfter",
                help="unix timestamp: tasks created after"),
            Arg("--created-before", key="createdBefore",
                help="unix timestamp: tasks created before"),
            Arg("--project-id", key="project_id", help="filter by project ID"),
        ]),
        "update": ("update_task", "Update task metadata", [
            Arg("task_id", help="task ID"),
            Arg("--title", help="new title"),
            Arg("--shared", key="enableShared", action="store_true",
                help="enable public sharing"),
            Arg("--no-shared", key="enableShared", action="store_false",
                help="disable public sharing"),
            Arg("--visible", key="enableVisibleInTaskList", action="store_true",
                help="show in task list"),
        ]),
        "delete": ("delete_task", "Permanently delete a task", [
            Arg("task_id", help="task ID"),
        ]),
        "wait": ("wait_for_task", "Poll until task completes or fails", [
            Arg("task_id", help="task ID"),
            Arg("--interval", type=int, default=DEFAULT_POLL_INTERVAL,
                help=f"poll interval in seconds (default: {DEFAULT_POLL_INTERVAL})"),
            Arg("--timeout", type=int, default=DEFAULT_POLL_TIMEOUT,
                help=f"max wait in seconds (default: {DEFAULT_POLL_TIMEOUT})"),
        ]),
    }),
    "files": ("Manage files", {
        "create": ("create_file", "Create file record and get upload URL", [
            Arg("filename", help="name for the file"),
        ]),
        "upload": ("upload_file", "Upload a local file (create record + PUT to S3)", [
            Arg("file_path", help="local file path to upload"),
        ]),
        "get": ("get_file", "Get file details", [
            Arg("file_id", help="file ID"),
        ]),
        "list": ("list_files", "List 10 most recent files", []),
        "delete": ("delete_file", "Delete a file and its S3 object", [
            Arg("file_id", help="file ID"),
        ]),
    }),
    "webhooks": ("Manage webhooks", {
        "create": ("create_webhook", "Register a webhook endpoint for task events", [
            Arg("--url", required=True, help="webhook endpoint URL"),
        ]),
        "delete": ("delete_webhook", "Remove a webhook", [
            Arg("webhook_id", help="webhook ID"),
        ]),
    }),
    "projects": ("Manage projects", {
        "create": ("create_project", "Create a project for organizing tasks", [
            Arg("--name", required=True, help="project name"),
            Arg("--instruction", help="default instruction applied to all tasks"),
        ]),
        "list": ("list_projects", "List all projects", [
            Arg("--limit", type=int, help="max results (1-1000, default: 100)"),
        ]),
    }),
}

# Extra flags not part of COMMANDS (handled in main)
_WAIT_ARGS: List[Arg] = [
    Arg("--wait", action="store_true", help="wait for task to complete after creating"),
    Arg("--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL,
        help=f"poll interval when --wait is used (default: {DEFAULT_POLL_INTERVAL})"),
    Arg("--poll-timeout", type=int, default=DEFAULT_POLL_TIMEOUT,
        help=f"max wait when --wait is used (default: {DEFAULT_POLL_TIMEOUT})"),
]

# ---------------------------------------------------------------------------
# CLI Builder + Dispatch
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build argparse parser from COMMANDS definition."""
    parser = argparse.ArgumentParser(
        prog="manus",
        description="Manus AI API CLI - zero-dependency client for all Manus endpoints.",
        epilog="Set MANUS_API_KEY environment variable before use. Get a key at https://manus.im",
    )
    parser.add_argument("--base-url", default=BASE_URL, help=argparse.SUPPRESS)

    resources = parser.add_subparsers(
        dest="resource", metavar="<resource>"
    )

    for res_name, (res_help, actions) in COMMANDS.items():
        rp = resources.add_parser(res_name, help=res_help)
        acts = rp.add_subparsers(dest="action", metavar="<action>")

        for act_name, (_, act_help, arg_defs) in actions.items():
            ap = acts.add_parser(act_name, help=act_help)
            for arg in arg_defs:
                ap.add_argument(arg.name, **arg.kwargs)

            # Add --wait flags to tasks create
            if res_name == "tasks" and act_name == "create":
                for arg in _WAIT_ARGS:
                    ap.add_argument(arg.name, **arg.kwargs)

    return parser


def dispatch(api: ManusAPI, resource: str, action: str, args: argparse.Namespace) -> Optional[JsonDict]:
    """Route parsed CLI args to the correct ManusAPI method."""
    method_name, _, arg_defs = COMMANDS[resource][1][action]
    kwargs: JsonDict = {}
    for arg in arg_defs:
        # Derive argparse dest from flag name: "--order-by" -> "order_by"
        dest: str = arg.name.lstrip("-").replace("-", "_")
        value = getattr(args, dest, None)
        api_key: str = arg.key or dest
        if value is not None:
            kwargs[api_key] = value
    return getattr(api, method_name)(**kwargs)


# ---------------------------------------------------------------------------
# Output Helpers
# ---------------------------------------------------------------------------


def _output(data: JsonDict) -> None:
    """Print JSON to stdout."""
    print(json.dumps(data, indent=2, default=str))


def _error(err: ManusError) -> None:
    """Print structured error JSON to stderr."""
    print(json.dumps(err.to_dict(), indent=2), file=sys.stderr)


def _progress(message: str) -> None:
    """Print progress to stderr (doesn't pollute JSON stdout)."""
    print(message, file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else None)

    if not getattr(args, "resource", None):
        parser.print_help()
        return 0

    if not getattr(args, "action", None):
        # Re-parse with just the resource to get its subparser help
        parser.parse_args([args.resource, "--help"])
        return 0  # pragma: no cover (--help exits)

    api_key: str = os.environ.get("MANUS_API_KEY", "")
    if not api_key:
        _error(ManusConfigError(
            "MANUS_API_KEY environment variable not set. "
            "Get your API key at https://manus.im and run: "
            "export MANUS_API_KEY=<your-key>"
        ))
        return 1

    client = ManusClient(api_key, args.base_url)
    api = ManusAPI(client)

    try:
        result = dispatch(api, args.resource, args.action, args)

        # Post-dispatch: tasks create --wait
        if args.resource == "tasks" and args.action == "create" and getattr(args, "wait", False):
            task_id = result.get("task_id")
            if task_id:
                _progress(f"Task created: {task_id}. Waiting for completion...")
                result = api.wait_for_task(
                    task_id,
                    interval=getattr(args, "poll_interval", DEFAULT_POLL_INTERVAL),
                    timeout=getattr(args, "poll_timeout", DEFAULT_POLL_TIMEOUT),
                )

        if result is not None:
            _output(result)
        else:
            # 204 No Content (e.g., webhook delete)
            _output({"ok": True})

        return 0

    except ManusError as e:
        _error(e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
