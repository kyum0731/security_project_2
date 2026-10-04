import json
from pathlib import Path
import unittest

from knitcode_analyzer_v2 import analyze_project
from knitcode_analyzer_v2.analyzer import validate_result
from .helpers import test_directory, write
from .evaluate import evaluate
from .input_cases import EVALUATION_FILES


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.root = self.enterContext(test_directory())
        for name, source in EVALUATION_FILES.items():
            write(self.root, name, source)

    def test_schema(self):
        from jsonschema import Draft202012Validator
        schema = json.loads((Path(__file__).parents[1] / "schemas" / "analysis.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        validator.validate(analyze_project(self.root))
        write(self.root, "broken.py", "def bad(:")
        validator.validate(analyze_project(self.root))

    def test_ranges_reproduce_expressions_and_ids_are_distinct(self):
        write(self.root, "unicode.py", 'def f(): pass\n한글 = "😊"; f(); f()\n')
        result = analyze_project(self.root)
        for edge in result["edges"]:
            if edge["type"] == "contains":
                self.assertNotIn("resolution_status", edge)
                continue
            r, path = edge["evidence"]["range"], edge["evidence"]["file"]
            lines = (self.root / path).read_text(encoding="utf-8").splitlines()
            segment = [s.encode("utf-8") for s in lines[r["start_line"]-1:r["end_line"]]]
            segment[-1] = segment[-1][:r["end_col"]]
            segment[0] = segment[0][r["start_col"]:]
            self.assertEqual(b"\n".join(segment).decode("utf-8"), edge["expression"])
        self.assertEqual(len({e["id"] for e in result["edges"]}), len(result["edges"]))
        self.assertTrue(all(n["id"].startswith("node:") for n in result["nodes"]))

    def test_determinism_and_to_dict_copy(self):
        a, b = analyze_project(self.root), analyze_project(self.root)
        c = a.to_dict()
        c["files"].clear()
        self.assertTrue(a["files"])
        for result in (a, b):
            result["metadata"].pop("analyzed_at")
            result["stats"].pop("analysis_seconds")
        self.assertEqual(a, b)

    def test_bad_reference_rejected(self):
        result = analyze_project(self.root)
        result["edges"][0]["target"] = "missing"
        with self.assertRaises(ValueError):
            validate_result(result)

    def test_bad_insight_reference_rejected(self):
        result = analyze_project(self.root)
        result["insights"]["reading_order"][0]["node_id"] = "missing"
        with self.assertRaises(ValueError):
            validate_result(result)

    def test_snapshot_changes_when_effective_resolution_scope_changes(self):
        write(self.root, "scope.py", "import hidden\nhidden.run()")
        (self.root / "hidden").mkdir()
        first = analyze_project(self.root)
        second = analyze_project(self.root, excluded_paths=(self.root / "hidden",))
        self.assertEqual(first["files"], second["files"])
        self.assertNotEqual(first["edges"], second["edges"])
        self.assertNotEqual(first["metadata"]["snapshot_id"], second["metadata"]["snapshot_id"])

    def test_metrics_include_unsupported_false_negative(self):
        metrics = evaluate()
        self.assertEqual(metrics["call_count"], 7)
        self.assertEqual(metrics["true_positive"], 4)
        self.assertEqual(metrics["false_positive"], 0)
        self.assertEqual(metrics["false_negative"], 1)
        self.assertEqual(metrics["precision"], 1)
        self.assertEqual(metrics["recall"], .8)
