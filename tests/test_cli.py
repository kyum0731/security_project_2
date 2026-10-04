import json
import unittest
from .helpers import test_directory, write, run_cli


class CliTests(unittest.TestCase):
    def setUp(self):
        self.root = self.enterContext(test_directory())
        self.project = self.root / "한글 프로젝트 with spaces"
        self.project.mkdir()

    def test_stdout_and_no_artifacts(self):
        write(self.project, "app.py", "def f(): pass\nf()")
        p = run_cli(self.project, "--json-stdout")
        self.assertEqual(p.returncode, 0, p.stderr)
        result = json.loads(p.stdout)
        self.assertEqual(result["stats"]["call_count"], 1)
        self.assertEqual(sorted(x.name for x in self.project.iterdir()), ["app.py"])

    def test_reports_and_auto_exclusion(self):
        write(self.project, "app.py", "pass")
        output = self.project / "reports"
        write(output, "do_not_analyze.py", "bad(")
        p = run_cli(self.project, "--report-dir", output)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, "")
        result = json.loads((output / "analysis.json").read_text(encoding="utf-8"))
        self.assertEqual(result["stats"]["file_count"], 1)
        self.assertEqual(result["metadata"]["coverage"]["skipped"][0]["reason"], "output_directory")

    def test_strict_partial_empty_unresolved(self):
        self.assertEqual(run_cli(self.project, "--strict", "--json-stdout").returncode, 1)
        write(self.project, "bad.py", "bad(")
        p = run_cli(self.project, "--strict", "--json-stdout")
        self.assertEqual(p.returncode, 1, p.stderr)
        self.assertEqual(json.loads(p.stdout)["metadata"]["analysis_status"], "partial")
        self.assertEqual(run_cli(self.project, "--json-stdout").returncode, 0)
        write(self.project, "bad.py", "unknown()")
        self.assertEqual(run_cli(self.project, "--strict", "--json-stdout").returncode, 0)

    def test_invalid_args_and_protected_output(self):
        for args in ((), (self.root / "missing",), (self.project, "--source-root", ".."),
                     (self.project, "--report-dir", self.project),
                     (self.project, "--json-stdout", "--report-dir", self.root / "reports")):
            with self.subTest(args=args):
                self.assertEqual(run_cli(*args).returncode, 2)

    def test_source_root_and_repeat_excludes(self):
        write(self.project, "src/app.py", "pass")
        write(self.project, "src/tests/a.py", "pass")
        write(self.project, "src/generated/b.py", "pass")
        write(self.project, "outside.py", "bad(")
        p = run_cli(self.project, "--source-root", "src", "--exclude", "src/tests/", "--exclude", "**/generated/**", "--json-stdout")
        self.assertEqual(p.returncode, 0, p.stderr)
        result = json.loads(p.stdout)
        self.assertEqual(result["metadata"]["coverage"]["scope"], "source_root_only")
        self.assertEqual(result["files"][0]["module"], "app")
        self.assertEqual(result["stats"]["file_count"], 1)
