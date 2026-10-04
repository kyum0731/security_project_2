import unittest
from knitcode_analyzer_v2 import analyze_project
from .helpers import test_directory, write


class InsightsTests(unittest.TestCase):
    def setUp(self):
        self.root = self.enterContext(test_directory())

    def test_entry_and_reading_evidence(self):
        write(self.root, "app.py", '"""Author description."""\ndef run():\n    run()\nif __name__ == "__main__":\n    run()\n')
        result = analyze_project(self.root)
        info = result["insights"]
        self.assertEqual(info["entry_points"][0]["rule"], "main_guard")
        self.assertEqual(info["entry_points"][0]["evidence"]["range"]["start_line"], 4)
        self.assertFalse(info["fallback_used"])
        self.assertEqual(len(info["reading_order"]), 2)
        self.assertEqual(len(info["reading_limit"]["cycle_edge_ids"]), 1)
        self.assertEqual(info["components"][0]["documentation"]["kind"], "documented")
        self.assertEqual(info["metrics"][0]["caller_count"], 1)

    def test_main_name_not_entry_and_no_business_claim(self):
        write(self.root, "payment.py", "def main(): pass")
        info = analyze_project(self.root)["insights"]
        self.assertTrue(info["fallback_used"])
        self.assertEqual(info["entry_points"], [])
        self.assertIn("업무 목적은 정적 구조만으로 확인할 수 없습니다", info["overview"]["text"])

    def test_main_module_and_read_limit(self):
        write(self.root, "__main__.py", "\n".join(f"def f{i}(): pass" for i in range(25)) + "\n" + "\n".join(f"f{i}()" for i in range(25)))
        info = analyze_project(self.root)["insights"]
        self.assertEqual(info["entry_points"][0]["rule"], "main_module")
        self.assertEqual(len(info["reading_order"]), 20)
        self.assertEqual(info["reading_limit"]["omitted_node_count"], 6)

    def test_builtin_shadowing_and_annotation_context(self):
        write(self.root, "a.py", "sum([])\ndef f(sum):\n    sum([])\ndef g(x: list() = tuple()) -> str(): pass\ny: list() = []")
        result = analyze_project(self.root)
        calls = [e for e in result["edges"] if e["type"] == "calls"]
        self.assertEqual(calls[0]["resolution_status"], "builtin")
        self.assertEqual(calls[1]["reason"], "parameter_call")
        self.assertEqual(sum(e["context"] == "annotation" for e in calls), 3)
        self.assertEqual(sum(e["context"] == "definition_expression" for e in calls), 1)

    def test_class_construction_and_duplicate_import_positions(self):
        write(self.root, "a.py", "import os, os\nclass C: pass\nC()")
        result = analyze_project(self.root)
        self.assertEqual(len({e["id"] for e in result["edges"]}), len(result["edges"]))
        call = next(e for e in result["edges"] if e["type"] == "calls")
        self.assertEqual(next(n for n in result["nodes"] if n["id"] == call["target"])["type"], "class")
