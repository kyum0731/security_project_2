"""Resolution regressions ported from prototype; input code exists only in temp dirs."""
import json
import sys
import textwrap
import unittest
from knitcode_analyzer_v2 import analyze_project as analyze_raw
from tests.helpers import test_directory, readable_result, write_json


def analyze_project(*args, **kwargs):
    return readable_result(analyze_raw(*args, **kwargs))


class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.root = self.enterContext(test_directory())

    def write(self, name, source):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source).lstrip("\n"), encoding="utf-8")
        return path

    def analyze(self, **kwargs):
        return analyze_project(self.root, **kwargs)

    @staticmethod
    def calls(result):
        return [e for e in result["edges"] if e["type"] == "calls"]

    def test_same_name_other_file_is_not_linked(self):
        self.write("one.py", "def helper(): pass")
        self.write("two.py", "helper()")
        self.assertEqual(self.calls(self.analyze())[0]["reason"], "name_not_found")

    def test_parameter_and_assignment_shadowing(self):
        self.write("m.py", """
            def helper(): pass
            def parameter(helper):
                helper()
            def assigned():
                helper()
                helper = 3
            def loop(values):
                for helper in values:
                    helper()
        """)
        self.assertEqual([e["reason"] for e in self.calls(self.analyze())],
                         ["parameter_call", "shadowed_name", "shadowed_name"])

    def test_nested_calls_have_one_owner_and_closures_are_unresolved(self):
        self.write("m.py", """
            def helper(): pass
            def outer():
                def inner():
                    helper()
                    inner()
                inner()
        """)
        calls = self.calls(self.analyze())
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0]["source"], "m.py::outer.inner@3:4")
        self.assertEqual(calls[0]["target"], "m.py::helper@1:0")
        self.assertEqual(calls[1]["reason"], "unsupported_syntax")
        self.assertEqual(calls[2]["target"], "m.py::outer.inner@3:4")

    def test_assignment_is_not_call(self):
        self.write("m.py", "def helper(): pass\nhandler = helper")
        self.assertEqual(self.calls(self.analyze()), [])

    def test_dynamic_nested_calls_are_preserved(self):
        self.write("m.py", """
            def factory(): pass
            def f(obj, name):
                obj.method()
                super().method()
                getattr(obj, name)()
                factory()()
        """)
        calls = self.calls(self.analyze())
        self.assertEqual(len(calls), 7)
        self.assertEqual(sum(e["resolution_status"] == "resolved" for e in calls), 1)
        self.assertTrue(any(e["expression"] == "factory()()" and e["reason"] == "dynamic_dispatch" for e in calls))

    def test_parse_failure_keeps_other_files(self):
        self.write("broken.py", "def broken(:")
        self.write("valid.py", "def helper(): pass\nhelper()")
        result = self.analyze()
        self.assertEqual(result["stats"]["parse_failed_file_count"], 1)
        self.assertEqual(result["stats"]["calls_by_status"]["resolved"], 1)
        self.assertEqual(result["diagnostics"][0]["code"], "syntax_error")

    def test_deletion_and_move_reanalysis(self):
        old = self.write("old.py", "def helper(): pass\nhelper()")
        output = self.root / "analysis.json"
        write_json(self.analyze(), output)
        old.rename(self.root / "new.py")
        self.write("new.py", "pass")
        write_json(self.analyze(), output)
        result = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result["stats"]["definition_count"], 0)
        self.assertEqual(result["edges"], [])
        self.assertEqual([n["file"] for n in result["nodes"]], ["new.py"])

    def test_deterministic_core(self):
        self.write("m.py", "def helper(): pass\nhelper()")
        first, second = self.analyze(), self.analyze()
        for result in (first, second):
            result["metadata"].pop("analyzed_at")
            result["stats"].pop("analysis_seconds")
        self.assertEqual(first, second)

    def test_source_root_and_exclusions(self):
        self.write("src/pkg/__init__.py", "")
        self.write("src/pkg/a.py", "def f(): pass")
        self.write("src/pkg/b.py", "from .a import f\nf()")
        self.write("src/.venv/ignored.py", "ignored()")
        self.write("outside.py", "ignored()")
        self.write("src/tests/test_x.py", "pass")
        result = self.analyze(source_root="src")
        self.assertEqual(result["stats"]["file_count"], 4)
        self.assertEqual(self.calls(result)[0]["target"], "src/pkg/a.py::f@1:0")
        self.assertEqual(result["metadata"]["source_root"], "src")

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            analyze_project(self.root / "missing")
        with self.assertRaises(ValueError):
            self.analyze(source_root="..")

    def test_external_import_and_rebinding(self):
        self.write("m.py", """
            import external_library as lib
            from another_library import run as execute
            lib.run()
            execute()
            def changed(lib):
                lib.run()
        """)
        calls = self.calls(self.analyze())
        self.assertEqual(calls[0]["external_name"], "external_library.run")
        self.assertEqual(calls[1]["external_name"], "another_library.run")
        self.assertEqual(calls[2]["resolution_status"], "unresolved")

    def test_import_variants(self):
        self.write("pkg/__init__.py", "def entry(): pass")
        self.write("pkg/payment.py", "def calc(): pass")
        for index, (statement, call) in enumerate([
            ("import pkg.payment as p", "p.calc()"),
            ("import pkg.payment", "pkg.payment.calc()"),
            ("from pkg import payment as p", "p.calc()"),
            ("from pkg.payment import calc", "calc()"),
            ("from pkg.payment import calc as c", "c()"),
            ("import pkg", "pkg.entry()"),
        ]):
            self.write(f"client{index}.py", statement + "\n" + call)
        calls = self.calls(self.analyze())
        self.assertEqual(len(calls), 6)
        self.assertTrue(all(e["resolution_status"] == "resolved" for e in calls))

    def test_relative_import_parent_package(self):
        self.write("pkg/__init__.py", "")
        self.write("pkg/a.py", "def f(): pass")
        self.write("pkg/sub/__init__.py", "")
        self.write("pkg/sub/b.py", "from ..a import f\nf()")
        self.assertEqual(self.calls(self.analyze())[0]["target"], "pkg/a.py::f@1:0")

    def test_duplicate_conditional_decorated_and_early_definitions(self):
        self.write("m.py", """
            def duplicate(): pass
            def duplicate(): pass
            if flag:
                def conditional(): pass
            @decorator
            def decorated(): pass
            duplicate()
            conditional()
            decorated()
            later()
            def later(): pass
        """)
        self.assertEqual([e["reason"] for e in self.calls(self.analyze())],
                         ["ambiguous_definition", "ambiguous_definition", "unsupported_syntax", "unsupported_syntax"])

    def test_ambiguous_modules(self):
        self.write("payment.py", "def calc(): pass")
        self.write("payment/__init__.py", "def calc(): pass")
        self.write("m.py", "from payment import calc\ncalc()")
        self.assertEqual(self.calls(self.analyze())[0]["reason"], "ambiguous_module")

    def test_reexports_wildcard_and_invalid_relative_import(self):
        self.write("a.py", "def helper(): pass")
        self.write("b.py", "from a import helper")
        self.write("m.py", "from b import helper\nhelper()")
        self.write("star.py", "from a import *\nhelper()")
        self.write("relative.py", "from .a import helper\nhelper()")
        self.assertTrue(all(e["resolution_status"] == "unresolved" for e in self.calls(self.analyze())))

    def test_module_and_class_body_ownership(self):
        self.write("m.py", """
            def helper(): pass
            helper()
            class C:
                helper()
                def method(self):
                    helper()
        """)
        calls = self.calls(self.analyze())
        self.assertEqual([e["source"] for e in calls],
                         ["m.py::<module>@1:0", "m.py::C@3:0", "m.py::C.method@5:4"])
        self.assertTrue(all(e["resolution_status"] == "resolved" for e in calls))

    def test_method_does_not_see_class_lexical_names(self):
        self.write("m.py", "class C:\n    def helper(): pass\n    def f(self): helper()")
        self.assertEqual(self.calls(self.analyze())[0]["reason"], "name_not_found")

    def test_unicode_byte_offsets(self):
        self.write("m.py", 'def helper(): pass\n한글 = "값"; helper()\n')
        edge = self.calls(self.analyze())[0]
        self.assertEqual(edge["evidence"]["col"], len('한글 = "값"; '.encode("utf-8")))
        self.assertEqual(edge["expression"], "helper()")

    def test_parameters_async_and_docstring(self):
        self.write("m.py", """
            async def f(a: str, /, b=3, *args: int, c: bool=True, **kwargs) -> str:
                """ + "'An async function.'" + """
                pass
        """)
        node = next(n for n in self.analyze()["nodes"] if n["type"] == "function")
        self.assertTrue(node["is_async"])
        self.assertEqual(node["docstring"], "An async function.")
        self.assertEqual(node["returns"], "str")
        self.assertEqual([p["name"] for p in node["parameters"]], ["a", "b", "args", "c", "kwargs"])
        self.assertEqual(node["parameters"][0]["annotation"], "str")
        self.assertEqual(node["parameters"][1]["default"], "3")
        self.assertEqual(node["parameters"][3]["default"], "True")

    def test_defining_expressions_belong_to_parent(self):
        self.write("m.py", "def helper(): pass\ndef f(x=helper()): pass")
        edge = self.calls(self.analyze())[0]
        self.assertEqual(edge["source"], "m.py::<module>@1:0")

    def test_definition_is_not_available_in_its_own_default(self):
        self.write("m.py", "def f(x=f()): pass\nclass C:\n    later()\ndef later(): pass")
        self.assertTrue(all(e["reason"] == "unsupported_syntax" for e in self.calls(self.analyze())))

    def test_repeated_call_sites_remain_separate(self):
        self.write("m.py", "def f(): pass\nf()\nf()")
        calls = self.calls(self.analyze())
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["target"], calls[1]["target"])
        self.assertEqual([e["evidence"]["line"] for e in calls], [2, 3])

    def test_import_from_broken_file_is_unresolved(self):
        self.write("broken.py", "def invalid(:")
        self.write("m.py", "from broken import invalid\ninvalid()")
        self.assertEqual(self.calls(self.analyze())[0]["reason"], "parse_error")

    def test_import_alias_reassignment(self):
        self.write("a.py", "def f(): pass")
        self.write("m.py", "from a import f\nf = callback\nf()")
        self.assertEqual(self.calls(self.analyze())[0]["reason"], "shadowed_name")

    def test_type_parameter_shadows_module_name(self):
        self.write("m.py", "def helper(): pass\ndef generic[helper]():\n    helper()")
        self.assertEqual(self.calls(self.analyze())[0]["reason"], "unsupported_syntax")

    def test_comprehensions_and_lambda_shadowing(self):
        self.write("m.py", """
            def helper(): pass
            values = [helper() for helper in callbacks]
            helper()
            f = lambda helper: helper()
        """)
        calls = self.calls(self.analyze())
        self.assertEqual([e["resolution_status"] for e in calls], ["unresolved", "resolved", "unresolved"])
        self.assertEqual(calls[2]["reason"], "parameter_call")

    def test_except_with_pattern_and_delete_bindings(self):
        snippets = [
            "try:\n    pass\nexcept Exception as helper:\n    helper()",
            "with resource as helper:\n    helper()",
            "match value:\n    case {'x': helper}:\n        helper()",
            "del helper\nhelper()",
        ]
        for index, snippet in enumerate(snippets):
            self.write(f"m{index}.py", "def helper(): pass\n" + snippet)
        self.assertTrue(all(e["reason"] == "shadowed_name" for e in self.calls(self.analyze())))

    def test_global_and_nonlocal_mutation(self):
        self.write("m.py", """
            def helper(): pass
            def mutate():
                global helper
                helper = 3
            def outer():
                def mutate_inner():
                    nonlocal local
                    local = 3
                def local(): pass
                local()
            helper()
        """)
        self.assertTrue(all(e["reason"] == "shadowed_name" for e in self.calls(self.analyze())))

    def test_source_is_never_executed(self):
        marker = self.root / "must_not_exist"
        self.write("m.py", f"raise RuntimeError('do not execute')\nopen({str(marker)!r}, 'w').close()")
        self.analyze()
        self.assertFalse(marker.exists())

    def test_encoding_cookie_and_decode_error(self):
        (self.root / "latin.py").write_bytes(b"# coding: latin-1\n# caf\xe9\ndef f(): pass\nf()\n")
        (self.root / "bad.py").write_bytes(b"# coding: utf-8\n\xff")
        result = self.analyze()
        self.assertEqual(result["stats"]["parse_failed_file_count"], 1)
        self.assertEqual(result["stats"]["calls_by_status"]["resolved"], 1)
