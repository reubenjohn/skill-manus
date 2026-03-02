#!/usr/bin/env python3
"""
Unit tests for manus.py. Uses unittest with no external dependencies.

Run: python3 -m pytest tests/ -v      (from the manus/ directory)
 or: python3 -m unittest tests.test_manus -v
"""

import json
import os
import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

# Ensure manus.py is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import manus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def mock_response(status=200, body=None):
    """Create a mock urllib response with context manager support."""
    resp = MagicMock()
    resp.status = status
    raw = json.dumps(body).encode("utf-8") if body is not None else b""
    resp.read.return_value = raw
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def mock_http_error(code, body=None):
    """Create a mock urllib.error.HTTPError."""
    err = urllib.error.HTTPError(
        url="https://api.manus.ai/v1/test",
        code=code,
        msg="Error",
        hdrs={},
        fp=BytesIO(json.dumps(body).encode("utf-8") if body else b"{}"),
    )
    return err


import urllib.error


# ---------------------------------------------------------------------------
# ManusClient Tests
# ---------------------------------------------------------------------------


class TestManusClient(unittest.TestCase):
    """Test the low-level HTTP client."""

    def setUp(self):
        self.client = manus.ManusClient("test-key-123")

    @patch("urllib.request.urlopen")
    def test_sets_api_key_header(self, mock_urlopen):
        mock_urlopen.return_value = mock_response(200, {"ok": True})
        self.client.request("GET", "/v1/tasks")
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.get_header("Api_key"), "test-key-123")

    @patch("urllib.request.urlopen")
    def test_sets_accept_header(self, mock_urlopen):
        mock_urlopen.return_value = mock_response(200, {"ok": True})
        self.client.request("GET", "/v1/tasks")
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.get_header("Accept"), "application/json")

    @patch("urllib.request.urlopen")
    def test_get_request_no_body(self, mock_urlopen):
        mock_urlopen.return_value = mock_response(200, {"id": "t1"})
        result = self.client.request("GET", "/v1/tasks/t1")
        req = mock_urlopen.call_args[0][0]
        self.assertIsNone(req.data)
        self.assertEqual(result, {"id": "t1"})

    @patch("urllib.request.urlopen")
    def test_post_sends_json_body(self, mock_urlopen):
        mock_urlopen.return_value = mock_response(200, {"task_id": "t1"})
        self.client.request("POST", "/v1/tasks", body={"prompt": "hello"})
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.get_header("Content-type"), "application/json")
        self.assertEqual(json.loads(req.data), {"prompt": "hello"})

    @patch("urllib.request.urlopen")
    def test_query_params_appended(self, mock_urlopen):
        mock_urlopen.return_value = mock_response(200, {"data": []})
        self.client.request("GET", "/v1/tasks", query={"limit": 10, "order": "desc"})
        req = mock_urlopen.call_args[0][0]
        self.assertIn("limit=10", req.full_url)
        self.assertIn("order=desc", req.full_url)

    @patch("urllib.request.urlopen")
    def test_query_params_with_list(self, mock_urlopen):
        """Array params like status should be encoded with doseq."""
        mock_urlopen.return_value = mock_response(200, {"data": []})
        self.client.request("GET", "/v1/tasks",
                            query={"status": ["completed", "running"]})
        req = mock_urlopen.call_args[0][0]
        self.assertIn("status=completed", req.full_url)
        self.assertIn("status=running", req.full_url)

    @patch("urllib.request.urlopen")
    def test_none_query_params_filtered(self, mock_urlopen):
        mock_urlopen.return_value = mock_response(200, {"data": []})
        self.client.request("GET", "/v1/tasks",
                            query={"limit": 10, "after": None})
        req = mock_urlopen.call_args[0][0]
        self.assertIn("limit=10", req.full_url)
        self.assertNotIn("after", req.full_url)

    @patch("urllib.request.urlopen")
    def test_204_returns_none(self, mock_urlopen):
        mock_urlopen.return_value = mock_response(204)
        result = self.client.request("DELETE", "/v1/webhooks/wh1")
        self.assertIsNone(result)

    @patch("urllib.request.urlopen")
    def test_http_error_raises_manus_api_error(self, mock_urlopen):
        mock_urlopen.side_effect = mock_http_error(
            404, {"message": "Task not found"}
        )
        with self.assertRaises(manus.ManusAPIError) as ctx:
            self.client.request("GET", "/v1/tasks/bad_id")
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.method, "GET")
        self.assertIn("404", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_http_error_includes_detail(self, mock_urlopen):
        mock_urlopen.side_effect = mock_http_error(
            401, {"message": "Invalid API key"}
        )
        with self.assertRaises(manus.ManusAPIError) as ctx:
            self.client.request("GET", "/v1/tasks")
        self.assertIn("Invalid API key", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_url_error_raises_manus_api_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        with self.assertRaises(manus.ManusAPIError) as ctx:
            self.client.request("GET", "/v1/tasks")
        self.assertIn("Connection failed", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_custom_base_url(self, mock_urlopen):
        client = manus.ManusClient("key", base_url="https://custom.api.com/")
        mock_urlopen.return_value = mock_response(200, {})
        client.request("GET", "/v1/tasks")
        req = mock_urlopen.call_args[0][0]
        self.assertTrue(req.full_url.startswith("https://custom.api.com/v1/tasks"))


# ---------------------------------------------------------------------------
# ManusAPI Tests
# ---------------------------------------------------------------------------


class TestManusAPI(unittest.TestCase):
    """Test high-level API methods."""

    def setUp(self):
        self.client = MagicMock(spec=manus.ManusClient)
        self.api = manus.ManusAPI(self.client)

    def test_create_task_minimal(self):
        self.client.request.return_value = {"task_id": "t1"}
        result = self.api.create_task("Write a report")
        self.client.request.assert_called_once_with(
            "POST", "/v1/tasks", body={"prompt": "Write a report"}
        )
        self.assertEqual(result["task_id"], "t1")

    def test_create_task_with_all_options(self):
        self.client.request.return_value = {"task_id": "t1"}
        self.api.create_task(
            "Analyze data",
            agentProfile="manus-1.6-max",
            taskMode="agent",
            attachments=["file1", "file2"],
            connectors=["gmail"],
            hideInTaskList=True,
            createShareableLink=True,
            taskId="prev_t1",
            locale="en-US",
            projectId="proj1",
            interactiveMode=True,
        )
        body = self.client.request.call_args[1]["body"]
        self.assertEqual(body["prompt"], "Analyze data")
        self.assertEqual(body["agentProfile"], "manus-1.6-max")
        self.assertEqual(body["taskMode"], "agent")
        self.assertEqual(len(body["attachments"]), 2)
        self.assertEqual(body["attachments"][0]["file_id"], "file1")
        self.assertTrue(body["hideInTaskList"])
        self.assertTrue(body["createShareableLink"])
        self.assertEqual(body["taskId"], "prev_t1")
        self.assertEqual(body["locale"], "en-US")
        self.assertEqual(body["projectId"], "proj1")
        self.assertTrue(body["interactiveMode"])

    def test_get_task(self):
        self.client.request.return_value = {"id": "t1", "status": "completed"}
        result = self.api.get_task("t1")
        self.client.request.assert_called_once_with(
            "GET", "/v1/tasks/t1", query=None
        )
        self.assertEqual(result["status"], "completed")

    def test_get_task_with_convert(self):
        self.client.request.return_value = {"id": "t1"}
        self.api.get_task("t1", convert=True)
        self.client.request.assert_called_once_with(
            "GET", "/v1/tasks/t1", query={"convert": "true"}
        )

    def test_list_tasks_no_filters(self):
        self.client.request.return_value = {"data": [], "has_more": False}
        self.api.list_tasks()
        self.client.request.assert_called_once_with(
            "GET", "/v1/tasks", query=None
        )

    def test_list_tasks_with_filters(self):
        self.client.request.return_value = {"data": []}
        self.api.list_tasks(
            limit=10, order="desc", status=["completed", "running"],
            project_id="proj1"
        )
        query = self.client.request.call_args[1]["query"]
        self.assertEqual(query["limit"], 10)
        self.assertEqual(query["order"], "desc")
        self.assertEqual(query["status"], ["completed", "running"])
        self.assertEqual(query["project_id"], "proj1")

    def test_update_task(self):
        self.client.request.return_value = {"task_id": "t1", "task_title": "New"}
        self.api.update_task("t1", title="New", enableShared=True)
        self.client.request.assert_called_once_with(
            "PUT", "/v1/tasks/t1",
            body={"title": "New", "enableShared": True}
        )

    def test_delete_task(self):
        self.client.request.return_value = {"id": "t1", "deleted": True}
        result = self.api.delete_task("t1")
        self.client.request.assert_called_once_with("DELETE", "/v1/tasks/t1")
        self.assertTrue(result["deleted"])

    def test_create_file(self):
        self.client.request.return_value = {
            "id": "f1", "upload_url": "https://s3.example.com/upload"
        }
        result = self.api.create_file("report.pdf")
        self.client.request.assert_called_once_with(
            "POST", "/v1/files", body={"filename": "report.pdf"}
        )
        self.assertEqual(result["id"], "f1")

    def test_get_file(self):
        self.client.request.return_value = {"id": "f1", "status": "uploaded"}
        result = self.api.get_file("f1")
        self.client.request.assert_called_once_with("GET", "/v1/files/f1")

    def test_list_files(self):
        self.client.request.return_value = {"data": []}
        self.api.list_files()
        self.client.request.assert_called_once_with("GET", "/v1/files")

    def test_delete_file(self):
        self.client.request.return_value = {"id": "f1", "deleted": True}
        self.api.delete_file("f1")
        self.client.request.assert_called_once_with("DELETE", "/v1/files/f1")

    def test_create_webhook(self):
        self.client.request.return_value = {"webhook_id": "wh1"}
        result = self.api.create_webhook("https://example.com/hook")
        self.client.request.assert_called_once_with(
            "POST", "/v1/webhooks",
            body={"webhook": {"url": "https://example.com/hook"}}
        )

    def test_delete_webhook(self):
        self.client.request.return_value = None
        self.api.delete_webhook("wh1")
        self.client.request.assert_called_once_with("DELETE", "/v1/webhooks/wh1")

    def test_create_project(self):
        self.client.request.return_value = {"id": "proj1", "name": "Research"}
        result = self.api.create_project("Research", instruction="Be thorough")
        self.client.request.assert_called_once_with(
            "POST", "/v1/projects",
            body={"name": "Research", "instruction": "Be thorough"}
        )

    def test_create_project_no_instruction(self):
        self.client.request.return_value = {"id": "proj1"}
        self.api.create_project("Research")
        body = self.client.request.call_args[1]["body"]
        self.assertNotIn("instruction", body)

    def test_list_projects(self):
        self.client.request.return_value = {"data": []}
        self.api.list_projects(limit=50)
        self.client.request.assert_called_once_with(
            "GET", "/v1/projects", query={"limit": 50}
        )

    def test_list_projects_no_limit(self):
        self.client.request.return_value = {"data": []}
        self.api.list_projects()
        self.client.request.assert_called_once_with(
            "GET", "/v1/projects", query=None
        )


# ---------------------------------------------------------------------------
# Wait/Poll Tests
# ---------------------------------------------------------------------------


class TestWaitForTask(unittest.TestCase):
    """Test polling logic."""

    def setUp(self):
        self.client = MagicMock(spec=manus.ManusClient)
        self.api = manus.ManusAPI(self.client)

    @patch("time.sleep")
    @patch("time.time")
    def test_wait_returns_on_completed(self, mock_time, mock_sleep):
        mock_time.side_effect = [0, 0, 5, 10]  # start, check1, check2
        self.client.request.side_effect = [
            {"id": "t1", "status": "running"},
            {"id": "t1", "status": "completed", "output": []},
        ]
        result = self.api.wait_for_task("t1", interval=5, timeout=60)
        self.assertEqual(result["status"], "completed")
        mock_sleep.assert_called_with(5)

    @patch("time.sleep")
    @patch("time.time")
    def test_wait_returns_on_failed(self, mock_time, mock_sleep):
        mock_time.side_effect = [0, 0, 5]
        self.client.request.side_effect = [
            {"id": "t1", "status": "failed", "error": "Out of credits"},
        ]
        result = self.api.wait_for_task("t1", interval=5, timeout=60)
        self.assertEqual(result["status"], "failed")

    @patch("time.sleep")
    @patch("time.time")
    def test_wait_timeout_raises(self, mock_time, mock_sleep):
        # time() calls: start, elapsed1, elapsed2, elapsed3
        mock_time.side_effect = [0, 0, 300, 601]
        self.client.request.side_effect = [
            {"id": "t1", "status": "running"},
            {"id": "t1", "status": "running"},
            {"id": "t1", "status": "running"},
        ]
        with self.assertRaises(manus.ManusAPIError) as ctx:
            self.api.wait_for_task("t1", interval=5, timeout=600)
        self.assertIn("Timeout", str(ctx.exception))


# ---------------------------------------------------------------------------
# File Upload Tests
# ---------------------------------------------------------------------------


class TestFileUpload(unittest.TestCase):
    """Test file upload flow."""

    def setUp(self):
        self.client = MagicMock(spec=manus.ManusClient)
        self.api = manus.ManusAPI(self.client)

    @patch("urllib.request.urlopen")
    def test_upload_file_content(self, mock_urlopen):
        mock_urlopen.return_value = mock_response(200)
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"hello world")
            f.flush()
            try:
                self.api.upload_file_content("https://s3.example.com/upload", f.name)
                req = mock_urlopen.call_args[0][0]
                self.assertEqual(req.get_method(), "PUT")
                self.assertNotIn("Api_key", dict(req.headers))
                self.assertEqual(req.data, b"hello world")
            finally:
                os.unlink(f.name)

    def test_upload_file_content_missing_file(self):
        with self.assertRaises(manus.ManusConfigError):
            self.api.upload_file_content("https://s3.example.com/upload", "/nonexistent")

    @patch("urllib.request.urlopen")
    def test_upload_file_convenience(self, mock_urlopen):
        """upload_file = create_file + upload_file_content."""
        self.client.request.return_value = {
            "id": "f1",
            "upload_url": "https://s3.example.com/upload",
            "filename": "test.txt",
        }
        mock_urlopen.return_value = mock_response(200)
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"data")
            f.flush()
            try:
                result = self.api.upload_file(f.name)
                self.assertEqual(result["id"], "f1")
                # create_file was called
                self.client.request.assert_called_once()
                # upload PUT was made
                mock_urlopen.assert_called_once()
            finally:
                os.unlink(f.name)

    def test_upload_file_missing_file(self):
        with self.assertRaises(manus.ManusConfigError):
            self.api.upload_file("/no/such/file.pdf")


# ---------------------------------------------------------------------------
# CLI Parsing Tests
# ---------------------------------------------------------------------------


class TestCLI(unittest.TestCase):
    """Test argument parsing and dispatch."""

    def setUp(self):
        self.parser = manus.build_parser()

    def test_tasks_create_minimal(self):
        args = self.parser.parse_args(["tasks", "create", "--prompt", "hello"])
        self.assertEqual(args.resource, "tasks")
        self.assertEqual(args.action, "create")
        self.assertEqual(args.prompt, "hello")
        self.assertEqual(args.profile, "manus-1.6")

    def test_tasks_create_with_wait(self):
        args = self.parser.parse_args([
            "tasks", "create", "--prompt", "hello", "--wait",
            "--poll-interval", "10", "--poll-timeout", "300"
        ])
        self.assertTrue(args.wait)
        self.assertEqual(args.poll_interval, 10)
        self.assertEqual(args.poll_timeout, 300)

    def test_tasks_get(self):
        args = self.parser.parse_args(["tasks", "get", "task123"])
        self.assertEqual(args.task_id, "task123")

    def test_tasks_list_with_status(self):
        args = self.parser.parse_args([
            "tasks", "list", "--status", "completed", "running"
        ])
        self.assertEqual(args.status, ["completed", "running"])

    def test_tasks_wait(self):
        args = self.parser.parse_args(["tasks", "wait", "t1", "--timeout", "120"])
        self.assertEqual(args.task_id, "t1")
        self.assertEqual(args.timeout, 120)

    def test_files_upload(self):
        args = self.parser.parse_args(["files", "upload", "/path/to/file.pdf"])
        self.assertEqual(args.file_path, "/path/to/file.pdf")

    def test_webhooks_create(self):
        args = self.parser.parse_args([
            "webhooks", "create", "--url", "https://example.com/hook"
        ])
        self.assertEqual(args.url, "https://example.com/hook")

    def test_projects_create(self):
        args = self.parser.parse_args([
            "projects", "create", "--name", "Research",
            "--instruction", "Be detailed"
        ])
        self.assertEqual(args.name, "Research")
        self.assertEqual(args.instruction, "Be detailed")

    def test_no_args_prints_help(self):
        """No arguments should print help to stdout and return 0."""
        result = manus.main([])
        self.assertEqual(result, 0)

    def test_resource_only_prints_help(self):
        """Resource without action should print help and exit."""
        with self.assertRaises(SystemExit) as ctx:
            manus.main(["tasks"])
        self.assertEqual(ctx.exception.code, 0)

    def test_tasks_create_missing_prompt(self):
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["tasks", "create"])


# ---------------------------------------------------------------------------
# Dispatch Tests
# ---------------------------------------------------------------------------


class TestDispatch(unittest.TestCase):
    """Test dispatch routes args to correct API methods."""

    def setUp(self):
        self.client = MagicMock(spec=manus.ManusClient)
        self.api = manus.ManusAPI(self.client)
        self.parser = manus.build_parser()

    def test_dispatch_tasks_create(self):
        self.client.request.return_value = {"task_id": "t1"}
        args = self.parser.parse_args(["tasks", "create", "--prompt", "hello"])
        result = manus.dispatch(self.api, args.resource, args.action, args)
        self.assertEqual(result["task_id"], "t1")

    def test_dispatch_tasks_list_maps_keys(self):
        """Verify --order-by maps to order_by API kwarg."""
        self.client.request.return_value = {"data": []}
        args = self.parser.parse_args([
            "tasks", "list", "--order-by", "updated_at"
        ])
        manus.dispatch(self.api, args.resource, args.action, args)
        query = self.client.request.call_args[1]["query"]
        self.assertEqual(query["orderBy"], "updated_at")

    def test_dispatch_files_list(self):
        self.client.request.return_value = {"data": []}
        args = self.parser.parse_args(["files", "list"])
        manus.dispatch(self.api, args.resource, args.action, args)
        self.client.request.assert_called_once_with("GET", "/v1/files")

    def test_dispatch_webhooks_delete(self):
        self.client.request.return_value = None
        args = self.parser.parse_args(["webhooks", "delete", "wh123"])
        manus.dispatch(self.api, args.resource, args.action, args)
        self.client.request.assert_called_once_with("DELETE", "/v1/webhooks/wh123")


# ---------------------------------------------------------------------------
# Error Format Tests
# ---------------------------------------------------------------------------


class TestErrors(unittest.TestCase):
    """Test error formatting for LLM consumption."""

    def test_api_error_to_dict(self):
        err = manus.ManusAPIError(
            "Not found", status_code=404, method="GET",
            path="/v1/tasks/t1", body={"message": "Task not found"}
        )
        d = err.to_dict()
        self.assertTrue(d["error"])
        self.assertEqual(d["status_code"], 404)
        self.assertEqual(d["method"], "GET")
        self.assertEqual(d["path"], "/v1/tasks/t1")
        self.assertEqual(d["details"]["message"], "Task not found")

    def test_config_error_to_dict(self):
        err = manus.ManusConfigError("MANUS_API_KEY not set")
        d = err.to_dict()
        self.assertTrue(d["error"])
        self.assertIn("MANUS_API_KEY", d["message"])

    def test_api_error_without_body(self):
        err = manus.ManusAPIError("Server error", status_code=500, method="POST", path="/v1/tasks")
        d = err.to_dict()
        self.assertNotIn("details", d)


# ---------------------------------------------------------------------------
# Main Function Tests
# ---------------------------------------------------------------------------


class TestMain(unittest.TestCase):
    """Test main() entry point."""

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_api_key_returns_1(self):
        # Remove MANUS_API_KEY if present
        os.environ.pop("MANUS_API_KEY", None)
        exit_code = manus.main(["tasks", "list"])
        self.assertEqual(exit_code, 1)

    @patch("urllib.request.urlopen")
    @patch.dict(os.environ, {"MANUS_API_KEY": "test-key"})
    def test_successful_list(self, mock_urlopen):
        mock_urlopen.return_value = mock_response(200, {"data": [], "has_more": False})
        exit_code = manus.main(["tasks", "list"])
        self.assertEqual(exit_code, 0)

    @patch("urllib.request.urlopen")
    @patch.dict(os.environ, {"MANUS_API_KEY": "test-key"})
    def test_api_error_returns_1(self, mock_urlopen):
        mock_urlopen.side_effect = mock_http_error(401, {"message": "Unauthorized"})
        exit_code = manus.main(["tasks", "list"])
        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
