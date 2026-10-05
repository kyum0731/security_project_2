from html.parser import HTMLParser
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from knitcode_analyzer_v2 import analyze_project
from knitcode_analyzer_v2.exporter import write_report, verify_manifest
from knitcode_analyzer_v2.reports import render_html, render_markdown
from .helpers import test_directory, write


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.root = self.enterContext(test_directory())
        self.project = self.root / "input"
        self.project.mkdir()
        self.output = self.root / "reports"
        write(self.project, "app.py", '"""<script>alert(1)</script> & [x](bad)"""\ndef run():\n    return sum([])\nif __name__ == "__main__":\n    run()')

    def test_offline_escaping_links_and_shared_snapshot(self):
        result = analyze_project(self.project)
        write_report(result, self.output)
        self.assertTrue(verify_manifest(self.output))
        page = (self.output / "report.html").read_text(encoding="utf-8")
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("script-src 'sha256-", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("http://", page)
        self.assertNotIn("https://", page)
        for name in ("analysis.json", "report.md", "report.html"):
            self.assertIn(result["metadata"]["snapshot_id"], (self.output / name).read_text(encoding="utf-8"))
        class LinkParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids, self.links = [], []
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if "id" in attrs:
                    self.ids.append(attrs["id"])
                if "href" in attrs and attrs["href"].startswith("#"):
                    self.links.append(attrs["href"][1:])
        parser = LinkParser()
        parser.feed(page)
        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        self.assertTrue(set(parser.links) <= set(parser.ids))
        self.assertNotIn("<script>", render_markdown(result))

    def test_guard_user_files_and_other_project(self):
        self.output.mkdir()
        own = write(self.output, "report.md", "my notes")
        result = analyze_project(self.project)
        with self.assertRaises(ValueError):
            write_report(result, self.output)
        self.assertEqual(own.read_text(), "my notes")
        with self.assertRaises(ValueError):
            write_report(result, self.project)
        own.unlink()
        write_report(result, self.output)
        other = self.root / "other"
        other.mkdir()
        with self.assertRaises(ValueError):
            write_report(analyze_project(other), self.output)

    def test_move_delete_and_tamper(self):
        write_report(analyze_project(self.project), self.output)
        (self.project / "app.py").rename(self.project / "moved.py")
        write(self.project, "moved.py", "pass")
        write_report(analyze_project(self.project), self.output)
        result = json.loads((self.output / "analysis.json").read_text(encoding="utf-8"))
        self.assertEqual(result["edges"], [])
        self.assertEqual([f["path"] for f in result["files"]], ["moved.py"])
        (self.output / "report.md").write_text("edited by user", encoding="utf-8")
        self.assertFalse(verify_manifest(self.output))
        with self.assertRaises(ValueError):
            write_report(analyze_project(self.project), self.output)

    def test_publish_failure_rolls_back(self):
        import os
        first = analyze_project(self.project)
        write_report(first, self.output)
        before = {p.name: p.read_bytes() for p in self.output.iterdir()}
        write(self.project, "extra.py", "pass")
        original = os.replace
        def fail(src, dst):
            if Path(dst).name == "report.html":
                raise OSError("simulated disk failure")
            return original(src, dst)
        with patch("knitcode_analyzer_v2.exporter.os.replace", side_effect=fail):
            with self.assertRaises(OSError):
                write_report(analyze_project(self.project), self.output)
        self.assertTrue(verify_manifest(self.output))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.output.iterdir()})

    def test_lock_and_untrusted_manifest(self):
        self.output.mkdir()
        (self.output / ".knitcode.lock").write_text("another process")
        with self.assertRaises(ValueError):
            write_report(analyze_project(self.project), self.output)
        self.assertTrue((self.output / ".knitcode.lock").exists())
        (self.output / ".knitcode.lock").unlink()
        (self.output / "manifest.json").write_text("null")
        with self.assertRaises(ValueError):
            write_report(analyze_project(self.project), self.output)

    def test_empty_report(self):
        (self.project / "app.py").unlink()
        result = analyze_project(self.project)
        self.assertIn("Python 파일 없음", render_html(result))
        self.assertIn("Python 파일 없음", render_markdown(result))
