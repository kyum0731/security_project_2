import json
from html.parser import HTMLParser
from pathlib import Path
import unittest

from knitcode_analyzer_v2 import analyze_project
from knitcode_analyzer_v2.graph import graph_data
from knitcode_analyzer_v2.reports import render_html, render_markdown
from .helpers import test_directory, write


class SymbolRelationTests(unittest.TestCase):
    def analyze(self, source, **files):
        root = self.enterContext(test_directory())
        write(root, "app.py", source)
        for path, code in files.items():
            write(root, path, code)
        result = analyze_project(root)
        self.nodes = {n["id"]: n for n in result["nodes"]}
        return result

    def pairs(self, result, kind):
        return {(self.nodes[e["source"]]["qualified_name"], self.nodes[e["target"]]["qualified_name"])
                for e in result["edges"] if e["type"] == kind and e["target"]}

    def test_scoped_variables_parameters_reads_writes_delete(self):
        result = self.analyze('''
            value = 3
            def first(value):
                total = value
                total += value
                del total
            def second():
                return value
        ''')
        self.assertEqual(result["stats"]["definition_count"], 2)
        self.assertEqual(result["stats"]["variable_count"], 3)
        self.assertEqual(self.pairs(result, "reads"), {("first", "first.value"), ("first", "first.total"), ("second", "value")})
        self.assertEqual(self.pairs(result, "writes"), {("", "value"), ("first", "first.total")})
        self.assertEqual(self.pairs(result, "deletes"), {("first", "first.total")})
        self.assertEqual(self.pairs(result, "depends_on"), {("first.total", "first.value")})
        self.assertTrue(any(n.get("variable_kind") == "parameter" for n in self.nodes.values()))

    def test_global_nonlocal_and_class_scope(self):
        result = self.analyze('''
            count = 0
            def outer():
                count = 1
                def inner():
                    nonlocal count
                    count += 1
                return inner
            def change():
                global count
                count = 2
            class Box:
                count = 3
                def get(self):
                    return count
        ''')
        self.assertIn(("outer.inner", "outer.count"), self.pairs(result, "writes"))
        self.assertIn(("change", "count"), self.pairs(result, "writes"))
        self.assertIn(("Box.get", "count"), self.pairs(result, "reads"))
        self.assertNotIn(("Box.get", "Box.count"), self.pairs(result, "reads"))
        self.assertIn(("outer", "outer.inner"), self.pairs(result, "references"))

    def test_inheritance_imported_variables_and_references(self):
        result = self.analyze('''
            from base import Parent, LIMIT
            import base
            class Child(Parent):
                size = LIMIT
                def calculate(self, x):
                    return x + base.LIMIT
            def build():
                return Child()
        ''', **{"base.py": "LIMIT = 10\nclass Parent: pass\n"})
        self.assertEqual(self.pairs(result, "inherits"), {("Child", "Parent")})
        self.assertIn(("Child", "LIMIT"), self.pairs(result, "reads"))
        self.assertIn(("Child.calculate", "LIMIT"), self.pairs(result, "reads"))
        self.assertIn(("build", "Child"), self.pairs(result, "calls"))
        self.assertTrue(any(e["type"] == "imports" and e["target"] and self.nodes[e["target"]]["name"] == "LIMIT" for e in result["edges"]))
        from jsonschema import Draft202012Validator
        schema = json.loads((Path(__file__).parents[1] / "schemas/analysis.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(result)

    def test_unsupported_objects_factories_and_mixed_bindings_not_guessed(self):
        result = self.analyze('''
            def factory(): pass
            class Dynamic(factory()): pass
            def fn(): pass
            fn = 3
            def use(obj):
                obj.value = 1
                return obj.value, fn
            hidden = [item for item in range(3)]
            callback = lambda item: item
        ''')
        base = next(e for e in result["edges"] if e["type"] == "inherits")
        self.assertIsNone(base["target"])
        self.assertEqual(base["resolution_status"], "unresolved")
        self.assertFalse(any(n["name"] in {"value", "item"} for n in self.nodes.values()))
        self.assertNotIn(("use", "fn"), self.pairs(result, "references"))

    def test_unicode_positions_graph_and_all_evidence_anchors(self):
        result = self.analyze('''
            기준 = 3
            class Base: pass
            class Child(Base):
                값 = 기준
                def run(self, 인자):
                    결과 = 인자 + 기준
                    return 결과
        ''')
        page, md, graph = render_html(result), render_markdown(result), graph_data(result)
        class Parser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids, self.links = [], []
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if "id" in attrs:
                    self.ids.append(attrs["id"])
                if attrs.get("href", "").startswith("#"):
                    self.links.append(attrs["href"][1:])
        parser = Parser()
        parser.feed(page)
        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        self.assertTrue(set(parser.links) <= set(parser.ids))
        self.assertTrue({e["id"] for e in result["edges"]} <= set(parser.ids))
        self.assertEqual({eid for e in graph["symbol_edges"] for eid in e["edge_ids"]},
                         {e["id"] for e in result["edges"] if e["target"]})
        self.assertIn("```mermaid\nflowchart LR", md)
        self.assertIn('value="reads"', page)
        self.assertIn("이름 쓰기", md)

    def test_class_later_binding_does_not_claim_earlier_read(self):
        result = self.analyze('''
            value = 1
            class C:
                value = value
                other = value
        ''')
        reads = [e for e in result["edges"] if e["type"] == "reads"]
        self.assertEqual(len(reads), 1)
        self.assertEqual(self.nodes[reads[0]["target"]]["qualified_name"], "C.value")
        self.assertEqual(reads[0]["evidence"]["range"]["start_line"], 4)
