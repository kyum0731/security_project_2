import json
import subprocess
import sys
import unittest

from knitcode_analyzer_v2 import analyze_project
from knitcode_analyzer_v2.context import build_context, search
from .helpers import test_directory, write


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.root = self.enterContext(test_directory())
        self.file = write(self.root, "service.py", 'def price(items):\n    """상품 가격 계산"""\n    return sum(items)\n\ndef checkout():\n    return price([1, 2])\n')
        self.result = analyze_project(self.root)
        self.price = next(n for n in self.result["nodes"] if n["name"] == "price")

    def test_search_name_docstring_and_no_result(self):
        self.assertEqual(search(self.result, "price")[0]["node_id"], self.price["id"])
        self.assertEqual(search(self.result, "상품")[0]["node_id"], self.price["id"])
        self.assertEqual(search(self.result, "xxxxxxxxxxxx"), [])
        with self.assertRaises(ValueError):
            build_context(self.result, "xxxxxxxxxxxx")

    def test_sources_neighbors_unicode_positions_and_determinism(self):
        before = json.dumps(self.result, sort_keys=True)
        context = build_context(self.result, "price")
        self.assertEqual({e["name"] for e in context["evidence"]}, {"price", "checkout"})
        original = self.file.read_bytes().decode("utf-8")
        separator = "\r\n\r\n" if "\r\n" in original else "\n\n"
        self.assertEqual(context["evidence"][0]["source"], original.split(separator)[0])
        self.assertEqual(context, build_context(self.result, "price"))
        self.assertEqual(json.dumps(self.result, sort_keys=True), before)
        single = build_context(self.result, "설명해줘", node_id=self.price["id"], depth=0)
        self.assertEqual(len(single["evidence"]), 1)

    def test_change_and_budget_and_unknown_node(self):
        context = build_context(self.result, "price", max_nodes=1)
        self.assertEqual(len(context["evidence"]), 1)
        self.assertEqual(context["omitted"][0]["reason"], "node_budget")
        with self.assertRaises(ValueError):
            build_context(self.result, "price", node_id="nonexistent")
        self.file.write_text("pass", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "변경"):
            build_context(self.result, "price")
        write(self.root, "big.py", 'def large():\n    """' + "x" * 2000 + '\"\"\"\n    pass')
        context = build_context(analyze_project(self.root), "large", max_chars=1000)
        self.assertEqual(context["evidence"], [])
        self.assertEqual(context["omitted"][0]["reason"], "source_character_budget")

    def test_unicode_separator_is_not_a_python_line_break(self):
        source = 'def 문자():\r\n    return "한글😀\u2028문자"\r\n'
        self.file.write_bytes(source.encode("utf-8"))
        result = analyze_project(self.root)
        context = build_context(result, "문자")
        self.assertEqual(context["evidence"][0]["source"], source.removesuffix("\r\n"))

    def test_cli_search_context_and_no_accidental_network(self):
        for action in ("search", "context"):
            proc = subprocess.run([sys.executable, "-m", "knitcode_analyzer_v2.assist", action, str(self.root), "--query", "price"], capture_output=True, encoding="utf-8", timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("snapshot_id", json.loads(proc.stdout))
        self.assertFalse((self.root / "report.html").exists())


if __name__ == "__main__":
    unittest.main()
