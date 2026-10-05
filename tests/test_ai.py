import copy
import io
import json
import unittest
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch
from urllib.error import HTTPError

from knitcode_analyzer_v2 import analyze_project
from knitcode_analyzer_v2.ai import AIError, NoRedirect, endpoint_url, explain, validate_answer
from knitcode_analyzer_v2.context import build_context
from knitcode_analyzer_v2.assist import main
from knitcode_analyzer_v2.reports.ai_markdown import render_ai_markdown
from .helpers import test_directory, write


class AITests(unittest.TestCase):
    def setUp(self):
        self.root = self.enterContext(test_directory())
        write(self.root, "a.py", "def run(): return 1")
        self.result = analyze_project(self.root)
        self.context = build_context(self.result, "run")
        self.answer = {"claims": [{"text": "run은 1을 반환합니다.", "kind": "observation", "evidence_ids": ["E1"]}], "limitations": ["실행하지 않았습니다."], "suggested_relations": []}

    def body(self, answer=None, finish="stop"):
        return io.BytesIO(json.dumps({"choices": [{"finish_reason": finish, "message": {"content": json.dumps(answer or self.answer)}}]}).encode())

    def test_explanation_locations_and_static_immutability(self):
        before = copy.deepcopy(self.result)
        with patch("knitcode_analyzer_v2.ai.build_opener") as build:
            build.return_value.open.return_value = self.body()
            result = explain(self.context, base_url="https://example.invalid/v1", model="test-model", api_key="secret-test")
            request = build.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, "https://example.invalid/v1/chat/completions")
            self.assertEqual(request.get_header("Authorization"), "Bearer secret-test")
            self.assertEqual(result["answer"]["claims"][0]["verified_locations"][0]["file"], "a.py")
            self.assertNotIn("secret-test", json.dumps(result))
        self.assertEqual(self.result, before)

    def test_invalid_citations_relations_response_and_finish(self):
        for invalid in ("E999", None):
            answer = copy.deepcopy(self.answer)
            answer["claims"][0]["evidence_ids"] = [invalid]
            with self.assertRaises(AIError):
                validate_answer(answer, self.context)
        answer = copy.deepcopy(self.answer)
        answer["suggested_relations"] = [{"source": "invented", "target": "invented", "type": "calls", "explanation": "bad", "evidence_ids": ["E1"]}]
        with self.assertRaises(AIError):
            validate_answer(answer, self.context)
        for body in (io.BytesIO(b"not json"), self.body(finish="length")):
            with patch("knitcode_analyzer_v2.ai.build_opener") as build:
                build.return_value.open.return_value = body
                with self.assertRaises(AIError):
                    explain(self.context, base_url="http://localhost:1234/v1", model="test-model")

    def test_http_timeout_redirect_and_endpoint_guards(self):
        for url in ("http://example.com/v1", "https://user:key@example.com/v1", "https://example.com/v1?key=x"):
            with self.assertRaises(AIError):
                endpoint_url(url)
        with self.assertRaises(AIError):
            NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.invalid")
        for error in (TimeoutError(), HTTPError("https://example.invalid", 401, "secret-body", {}, None)):
            with patch("knitcode_analyzer_v2.ai.build_opener") as build:
                build.return_value.open.side_effect = error
                with self.assertRaises(AIError) as caught:
                    explain(self.context, base_url="http://127.0.0.1:1234/v1", model="test-model")
                self.assertNotIn("secret-body", str(caught.exception))
        with patch("knitcode_analyzer_v2.ai.build_opener") as build:
            with self.assertRaises(AIError):
                explain(self.context, base_url="https://example.invalid/v1", model="test-model")
            build.assert_not_called()

    def test_cli_failure_saved_and_existing_output_never_overwritten(self):
        output = self.root / "explanation.json"
        with patch("knitcode_analyzer_v2.ai.build_opener") as build, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            build.return_value.open.side_effect = TimeoutError()
            args = ["explain", str(self.root), "--query", "run", "--base-url", "http://127.0.0.1:1234/v1", "--model", "test-model", "--output", str(output)]
            self.assertEqual(main(args), 3)
            original = output.read_bytes()
            value = json.loads(original)
            self.assertEqual(value["status"], "failed")
            self.assertTrue(value["context"]["evidence"])
            self.assertEqual(main(args), 2)
            self.assertEqual(build.return_value.open.call_count, 1)
            self.assertEqual(output.read_bytes(), original)

    def test_oversized_selected_source_does_not_send(self):
        context = copy.deepcopy(self.context)
        context["evidence"] = []
        with patch("knitcode_analyzer_v2.ai.build_opener") as build:
            with self.assertRaises(AIError):
                explain(context, base_url="http://localhost:1234/v1", model="test-model")
            build.assert_not_called()

    def test_ollama_native_request_over_local_http(self):
        recorded = {}
        reply = {"done": True, "done_reason": "stop", "message": {"content": json.dumps(self.answer)}}
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                recorded.update(path=self.path, authorization=self.headers.get("Authorization"),
                                payload=json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                raw = json.dumps(reply).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            def log_message(self, *args):
                pass
        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        try:
            result = explain(self.context, base_url=f"http://127.0.0.1:{server.server_port}", model="local-test",
                             provider="ollama", api_key="do-not-forward", num_ctx=8192)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertEqual(result["provider"], "ollama_local")
        self.assertEqual(recorded["path"], "/api/chat")
        self.assertIsNone(recorded["authorization"])
        self.assertEqual(recorded["payload"]["format"], "json")
        self.assertEqual(recorded["payload"]["options"]["num_ctx"], 8192)
        self.assertNotIn("response_format", recorded["payload"])

    def test_ollama_guards_and_incomplete_response(self):
        for url in ("https://example.invalid", "http://localhost:11434/v1"):
            with self.assertRaises(AIError):
                endpoint_url(url, "ollama")
        with patch("knitcode_analyzer_v2.ai.build_opener") as build:
            with self.assertRaises(AIError):
                explain(self.context, base_url="http://localhost:11434", model="model:cloud", provider="ollama")
            build.assert_not_called()
            build.return_value.open.return_value = io.BytesIO(json.dumps({"done": True, "done_reason": "length"}).encode())
            with self.assertRaises(AIError):
                explain(self.context, base_url="http://localhost:11434", model="local-model", provider="ollama")

    def test_cli_ollama_settings_and_markdown_output(self):
        output, markdown = self.root / "result.json", self.root / "result.md"
        env = {"KNITCODE_AI_BASE_URL": "https://external.invalid/v1", "KNITCODE_AI_MODEL": "external-model", "KNITCODE_AI_API_KEY": "external-key"}
        with patch.dict("os.environ", env, clear=True), patch("knitcode_analyzer_v2.ai.build_opener") as build, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            build.return_value.open.return_value = io.BytesIO(json.dumps({"done": True, "done_reason": "stop", "message": {"content": json.dumps(self.answer)}}).encode())
            code = main(["explain", str(self.root), "--query", "run", "--provider", "ollama", "--model", "local-test", "--output", str(output), "--markdown-output", str(markdown)])
            self.assertEqual(code, 0)
            request = build.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
            self.assertIsNone(request.get_header("Authorization"))
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"], "complete")
        text = markdown.read_text(encoding="utf-8")
        self.assertIn("run은 1을 반환합니다", text)
        self.assertIn("E1", text)
        self.assertIn("def run(): return 1", text)

    def test_markdown_failure_escape_and_preflight(self):
        value = {"context": self.context, "status": "failed", "model": "local", "endpoint": "http://localhost", "snapshot_id": "snap", "input_hash": "hash", "error": "<script>[click](bad)</script>"}
        text = render_ai_markdown(value)
        self.assertNotIn("<script>", text)
        self.assertIn("설명 생성 실패", text)
        markdown = write(self.root, "existing.md", "my notes")
        with patch("knitcode_analyzer_v2.ai.build_opener") as build, redirect_stderr(io.StringIO()):
            code = main(["explain", str(self.root), "--query", "run", "--provider", "ollama", "--model", "local", "--markdown-output", str(markdown)])
            self.assertEqual(code, 2)
            build.assert_not_called()
        self.assertEqual(markdown.read_text(), "my notes")


if __name__ == "__main__":
    unittest.main()
