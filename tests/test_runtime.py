import copy
import json
from pathlib import Path
import sys
import subprocess
import unittest
from unittest.mock import patch
from contextlib import redirect_stderr
from io import StringIO

from knitcode_analyzer_v2.exporter import verify_manifest
from knitcode_analyzer_v2.graph import graph_data
from knitcode_analyzer_v2.runtime import main, read_events, run_project, verify_run
from .helpers import test_directory, write


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.root = self.enterContext(test_directory())
        self.project = self.root / "한글 project"
        self.project.mkdir()
        self.output = self.root / "reports"

    def run_target(self, source, **options):
        write(self.project, "main.py", source)
        return run_project(self.project, script="main.py", report_dir=self.output, **options)

    def test_method_recursion_counts_and_static_immutability(self):
        directory, runtime = self.run_target('''
            class Worker:
                def process(self): return 1
            def recurse(n):
                if n: return recurse(n - 1)
                return 0
            def run():
                obj = Worker()
                obj.process()
                obj.process()
                recurse(2)
            run()
        ''')
        self.assertEqual(runtime["run"]["execution_status"], "finished", (directory / "stderr.log").read_text(encoding="utf-8"))
        self.assertEqual(runtime["run"]["trace_status"], "complete_within_scope", runtime["run"])
        analysis = json.loads((directory / "analysis.json").read_text(encoding="utf-8"))
        names = {n["id"]: n["qualified_name"] for n in analysis["nodes"]}
        calls = runtime["summary"]["observed_calls"]
        self.assertEqual(sum(e["count"] for e in calls if names[e["target"]] == "Worker.process"), 2)
        self.assertEqual(sum(e["count"] for e in calls if names[e["source"]] == names[e["target"]] == "recurse"), 2)
        static = copy.deepcopy(analysis)
        graph = graph_data(analysis, runtime=runtime)
        self.assertEqual(analysis, static)
        self.assertTrue(any(e["type"] == "observed_calls" for e in graph["edges"]))
        self.assertTrue(any(e["expression"] == "obj.process()" and e["target"] is None for e in analysis["edges"] if e["type"] == "calls"))
        self.assertTrue(verify_manifest(directory))
        self.assertTrue(verify_run(directory))
        self.assertIn("실행 관측 결과", (directory / "report.html").read_text(encoding="utf-8"))

    def test_exception_handled_and_unhandled(self):
        directory, value = self.run_target('''
            def fail(): raise ValueError("not-in-events")
            try: fail()
            except ValueError: pass
        ''')
        self.assertEqual(value["run"]["execution_status"], "finished")
        self.assertTrue(value["summary"]["exceptions"])
        self.assertNotIn("not-in-events", (directory / "events.jsonl").read_text(encoding="utf-8"))
        directory, value = self.run_target('def fail(): raise RuntimeError("boom")\nfail()')
        self.assertEqual(value["run"]["execution_status"], "failed")
        self.assertEqual(value["run"]["target_exit_code"], 1)
        self.assertTrue(verify_run(directory))

    def test_arguments_cwd_module_and_test_runner(self):
        write(self.project, "pkg/__init__.py", "")
        write(self.project, "pkg/__main__.py", "import sys, pathlib\nprint(sys.argv[1])\nprint(pathlib.Path.cwd().name)")
        directory, value = run_project(self.project, module="pkg", args=["한글 argument"], report_dir=self.output)
        self.assertEqual(value["run"]["target_exit_code"], 0)
        log = (directory / "stdout.log").read_text(encoding="utf-8")
        self.assertIn("한글 argument", log)
        self.assertIn("한글 project", log)
        write(self.project, "test_app.py", "import unittest\nclass Test(unittest.TestCase):\n    def test_ok(self): self.assertEqual(2, 2)")
        directory, value = run_project(self.project, module="unittest", args=["discover", "-s", "."], report_dir=self.output)
        self.assertEqual(value["run"]["target_exit_code"], 0, (directory / "stderr.log").read_text())
        self.assertTrue(value["summary"]["node_entries"])

    def test_event_limit_timeout_and_log_budget(self):
        directory, value = self.run_target('def f(): pass\nfor i in range(100): f()\nprint("x" * 10000)', max_events=5, max_log_bytes=100)
        self.assertIn("event_limit", value["run"]["limitations"])
        self.assertLessEqual(len(value["events"]), 6)
        self.assertEqual((directory / "stdout.log").stat().st_size, 100)
        self.assertTrue(value["run"]["logs"]["stdout"]["truncated"])
        directory, value = self.run_target('import time\ndef wait(): time.sleep(5)\nwait()', timeout=0.5)
        self.assertEqual(value["run"]["execution_status"], "timeout")
        self.assertTrue(verify_run(directory))

    def test_async_thread_and_source_change_are_visible(self):
        directory, value = self.run_target('''
            import asyncio, threading
            def f(): return 1
            async def task(): f()
            asyncio.run(task())
            t = threading.Thread(target=f)
            t.start()
            t.join()
        ''')
        self.assertIn("async_or_generator_not_traced", value["run"]["limitations"])
        self.assertIn("other_thread_not_traced", value["run"]["limitations"])
        directory, value = self.run_target('from pathlib import Path\nPath(__file__).write_text("pass")')
        self.assertIn("source_changed", value["run"]["limitations"])

    def test_path_guards_fresh_runs_and_missing_python(self):
        write(self.project, "main.py", "pass")
        with self.assertRaises(ValueError):
            run_project(self.project, script="../missing.py", report_dir=self.output)
        with self.assertRaises(ValueError):
            run_project(self.project, script="main.py", report_dir=self.project)
        a, _ = run_project(self.project, script="main.py", report_dir=self.output)
        b, _ = run_project(self.project, script="main.py", report_dir=self.output)
        self.assertNotEqual(a, b)
        directory, value = run_project(self.project, script="main.py", report_dir=self.output, python=str(self.root / "missing-python.exe"))
        self.assertEqual(value["run"]["execution_status"], "launch_failed")
        self.assertTrue(verify_run(directory))

    def test_incomplete_last_event(self):
        file = self.root / "events.jsonl"
        file.write_bytes(b'{"seq":1,"event":"limitation","reason":"test"}\n{"seq":2')
        events, invalid = read_events(file, 10)
        self.assertEqual(len(events), 1)
        self.assertTrue(invalid)

    def test_decorated_nested_and_generated_code_not_guessed(self):
        directory, value = self.run_target('''
            def decorate(fn): return fn
            @decorate
            def outer():
                def inner(): return 1
                return inner()
            outer()
            exec(compile("def invented(): return 3\\ninvented()", __file__, "exec"))
        ''')
        analysis = json.loads((directory / "analysis.json").read_text(encoding="utf-8"))
        names = {n["id"]: n["qualified_name"] for n in analysis["nodes"]}
        self.assertTrue(any(names[e["target"]] == "outer.inner" for e in value["summary"]["observed_calls"]))
        self.assertIn("unmapped_project_code", value["run"]["limitations"])

    def test_child_process_notice_and_cli_argument_passthrough(self):
        write(self.project, "main.py", 'import subprocess, sys\ndef f(): print(sys.argv[1])\nf()\nsubprocess.run([sys.executable, "-c", "print(123)"], check=True)')
        captured = StringIO()
        with redirect_stderr(captured):
            code = main([str(self.project), "--script", "main.py", "--report-dir", str(self.output), "--", "--target-flag"])
        self.assertEqual(code, 1)  # target succeeded but child coverage is partial
        directory = next((self.output / "runs").iterdir())
        run = json.loads((directory / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(run["target_exit_code"], 0)
        self.assertIn("child_process_not_traced", run["limitations"])
        self.assertIn("--target-flag", (directory / "stdout.log").read_text())
        self.assertTrue(verify_run(directory))

    def test_cancel_preserves_partial_report(self):
        write(self.project, "main.py", "import time\ntime.sleep(10)")
        original = subprocess.Popen.wait
        calls = []
        def interrupt_once(process, *args, **kwargs):
            if not calls:
                calls.append(True)
                raise KeyboardInterrupt
            return original(process, *args, **kwargs)
        with patch.object(subprocess.Popen, "wait", interrupt_once):
            directory, value = run_project(self.project, script="main.py", report_dir=self.output)
        self.assertEqual(value["run"]["execution_status"], "cancelled")
        self.assertTrue(verify_run(directory))

    def test_caller_unicode_position_and_external_callback_boundary(self):
        directory, value = self.run_target('''
            from functools import reduce
            def add(a, b): return a + b
            def run():
                문자 = "😀"; add(1, 2); add(3, 4)
                reduce(add, [1, 2, 3])
            run()
        ''')
        analysis = json.loads((directory / "analysis.json").read_text(encoding="utf-8"))
        add = next(n["id"] for n in analysis["nodes"] if n["name"] == "add")
        direct = [e for e in value["summary"]["observed_calls"] if e["target"] == add]
        self.assertEqual(value["summary"]["node_entries"][add], 4)
        self.assertTrue(all(e["evidence"]["range"] is not None for e in direct))
        # Two direct calls on one line must remain different call sites.
        on_line = [e for e in direct if e["evidence"]["range"]["start_line"] == 4]
        self.assertEqual(len(on_line), 2)
        self.assertNotEqual(on_line[0]["evidence"]["range"], on_line[1]["evidence"]["range"])
        self.assertTrue(all(e["caller_relation"] == "python_frame_parent" for e in direct))


if __name__ == "__main__":
    unittest.main()
