import base64
import hashlib
from html.parser import HTMLParser
import json
import unittest

from knitcode_analyzer_v2 import analyze_project
from knitcode_analyzer_v2.graph import graph_data
from knitcode_analyzer_v2.reports import render_html
from knitcode_analyzer_v2.reports.graph import SCRIPT, script_hash
from .helpers import test_directory, write


class GraphTests(unittest.TestCase):
    def test_projection_preserves_real_edges_and_all_evidence(self):
        with test_directory() as root:
            write(root, "a.py", "from b import run\nrun()\nrun()\nunknown()")
            write(root, "b.py", "def run(): pass")
            result = analyze_project(root)
            before = json.dumps(result, sort_keys=True)
            graph = graph_data(result)
            nodes = {n["id"]: n for n in graph["nodes"]}
            original = {e["id"]: e for e in result["edges"]}
            call_group = next(e for e in graph["file_edges"] if e["type"] == "calls")
            self.assertEqual(len(call_group["edge_ids"]), 2)
            self.assertEqual(nodes[call_group["source"]]["file"], "a.py")
            self.assertEqual(nodes[call_group["target"]]["file"], "b.py")
            grouped = {eid for e in graph["file_edges"] for eid in e["edge_ids"]}
            self.assertEqual(grouped, {e["id"] for e in result["edges"] if e["target"] and e["type"] != "contains"})
            self.assertTrue(all(original[eid]["target"] in nodes for eid in grouped))
            self.assertEqual(json.dumps(result, sort_keys=True), before)

    def test_embedded_json_cannot_close_script_and_csp_matches(self):
        with test_directory() as root:
            write(root, "a.py", '\'\'\'</script><script>alert("x")</script>&\'\'\'\ndef run(): pass')
            result = analyze_project(root)
            page = render_html(result)
            class Scripts(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.scripts, self.current = [], None
                def handle_starttag(self, tag, attrs):
                    if tag == "script":
                        self.current = []
                def handle_data(self, text):
                    if self.current is not None:
                        self.current.append(text)
                def handle_endtag(self, tag):
                    if tag == "script":
                        self.scripts.append("".join(self.current))
                        self.current = None
            parser = Scripts()
            parser.feed(page)
            self.assertEqual(len(parser.scripts), 2)
            data, script = parser.scripts
            self.assertEqual(json.loads(data), graph_data(result))
            self.assertEqual(script, SCRIPT)
            self.assertEqual(base64.b64encode(hashlib.sha256(script.encode()).digest()).decode(), script_hash())
            self.assertNotIn("innerHTML", script)


if __name__ == "__main__":
    unittest.main()
