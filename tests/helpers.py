from contextlib import contextmanager
from pathlib import Path
import json
import shutil
import subprocess
import sys
import uuid
import textwrap

from knitcode_analyzer_v2 import analyze_project

BASE = (Path(__file__).resolve().parents[1] / "build" / "tests").resolve()


@contextmanager
def test_directory():
    BASE.mkdir(parents=True, exist_ok=True)
    path = (BASE / ("case-" + uuid.uuid4().hex)).resolve()
    path.mkdir()
    try:
        yield path
    finally:
        if path.parent != BASE or not path.name.startswith("case-"):
            raise RuntimeError("Test cleanup boundary mismatch")
        shutil.rmtree(path)


def write(root, name, source):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source).lstrip("\n"), encoding="utf-8")
    return path


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "knitcode_analyzer_v2", *map(str, args)],
                          capture_output=True, encoding="utf-8", timeout=60)


def readable_result(result):
    """Use readable legacy labels ONLY to compare inherited resolution expectations.

    Public hash IDs and nested ranges are tested without conversion in test_contract.
    """
    result = result.to_dict()
    mapping = {n["id"]: f"{n['file']}::{n['qualified_name'] or '<module>'}@{(n['range'] or {}).get('start_line', 1)}:{(n['range'] or {}).get('start_col', 0)}"
               for n in result["nodes"]}
    for node in result["nodes"]:
        node["id"] = mapping[node["id"]]
        if node["parent"]:
            node["parent"] = mapping[node["parent"]]
    for edge in result["edges"]:
        edge["source"] = mapping[edge["source"]]
        edge["target"] = mapping.get(edge["target"])
        r = edge["evidence"].pop("range")
        edge["evidence"].update(line=r["start_line"], col=r["start_col"], end_line=r["end_line"], end_col=r["end_col"])
    return result


def write_json(result, path):
    path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
