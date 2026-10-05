import copy
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch
from urllib.error import HTTPError

from knitcode_analyzer_v2 import analyze_project
from knitcode_analyzer_v2.ai import AIError, NoRedirect, endpoint_url, explain, validate_answer
from knitcode_analyzer_v2.context import build_context
from knitcode_analyzer_v2.assist import main
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


if __name__ == "__main__":
    unittest.main()
