import unittest
from unittest.mock import patch
from pathlib import Path

from knitcode_analyzer_v2 import analyze_project
from knitcode_analyzer_v2.scanner import compile_pattern
from .helpers import test_directory, write


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.root = self.enterContext(test_directory())

    def test_globs_and_nested_exclusions(self):
        for name in ("app.py", "tests/a.py", "src/generated/g.py", "generated/g.py", ".hidden/a.py", ".venv/a.py"):
            write(self.root, name, "pass")
        result = analyze_project(self.root, excludes=("tests/", "**/generated/**"))
        self.assertEqual([f["path"] for f in result["files"]], [".hidden/a.py", "app.py"])
        self.assertEqual(result["stats"]["skipped_directory_count"], 4)
        self.assertTrue(compile_pattern("src/?.py").fullmatch("src/a.py"))
        self.assertFalse(compile_pattern("src/*.py").fullmatch("src/nested/a.py"))
        for pattern in ("!a.py", "../x", "/x", "x\\y", ""):
            with self.assertRaises(ValueError):
                compile_pattern(pattern)

    def test_excluded_module_not_external(self):
        write(self.root, "hidden.py", "def run(): pass")
        write(self.root, "app.py", "import hidden\nhidden.run()")
        result = analyze_project(self.root, excludes=("hidden.py",))
        self.assertTrue(all(e["reason"] == "module_not_indexed" for e in result["edges"]))

    def test_empty_and_total_failure(self):
        self.assertEqual(analyze_project(self.root)["metadata"]["analysis_status"], "empty")
        write(self.root, "bad.py", "def bad(:")
        result = analyze_project(self.root)
        self.assertEqual(result["metadata"]["analysis_status"], "partial")
        self.assertEqual(result["files"][0]["parse_status"], "syntax_error")
        self.assertEqual(result["stats"]["resolution_rate"], None)

    def test_decode_and_read_errors(self):
        (self.root / "bad.py").write_bytes(b"# coding: utf-8\n\xff")
        path = write(self.root, "denied.py", "pass")
        original = Path.read_bytes
        def read(p):
            if p == path:
                raise PermissionError("test read failure")
            return original(p)
        with patch.object(Path, "read_bytes", read):
            result = analyze_project(self.root)
        self.assertEqual([f["parse_status"] for f in result["files"]], ["decode_error", "read_error"])
        self.assertTrue(all(n["range"] is None for n in result["nodes"]))

    def test_scan_error_is_partial_and_root_error_fatal(self):
        import os
        write(self.root, "app.py", "pass")
        write(self.root, "denied/a.py", "pass")
        original = os.scandir
        def scan(path):
            if Path(path).name == "denied":
                raise PermissionError("test denied")
            return original(path)
        with patch("knitcode_analyzer_v2.scanner.os.scandir", side_effect=scan):
            self.assertEqual(analyze_project(self.root)["metadata"]["analysis_status"], "partial")
        with patch("knitcode_analyzer_v2.scanner.os.scandir", side_effect=PermissionError("root")):
            with self.assertRaises(ValueError):
                analyze_project(self.root)

    def test_source_change_detected(self):
        path = write(self.root, "app.py", "pass")
        original = Path.read_bytes
        count = 0
        def read(p):
            nonlocal count
            value = original(p)
            if p == path:
                count += 1
                if count == 2:
                    return b"# modified"
            return value
        with patch.object(Path, "read_bytes", read):
            result = analyze_project(self.root)
        self.assertEqual(result["metadata"]["analysis_status"], "partial")
        self.assertIn("source_changed", [d["code"] for d in result["diagnostics"]])

    def test_actual_symlink(self):
        target = write(self.root, "app.py", "pass")
        try:
            (self.root / "link.py").symlink_to(target)
        except OSError as error:
            self.skipTest(f"Symbolic link permission unavailable: {error}")
        result = analyze_project(self.root)
        self.assertEqual(result["stats"]["file_count"], 1)
        self.assertEqual(result["metadata"]["coverage"]["skipped"][0]["reason"], "link_skipped")

    def test_junction_detection_without_privilege(self):
        write(self.root, "linked/app.py", "pass")
        with patch.object(Path, "is_junction", lambda p: p.name == "linked"):
            result = analyze_project(self.root)
        self.assertEqual(result["files"], [])
        self.assertEqual(result["metadata"]["coverage"]["skipped"][0]["reason"], "link_skipped")
