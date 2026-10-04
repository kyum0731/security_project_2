import json
from knitcode_analyzer_v2 import analyze_project
from .helpers import test_directory, write
from .input_cases import EVALUATION_FILES, EXPECTED_CALLS


def evaluate():
    with test_directory() as root:
        for name, source in EVALUATION_FILES.items():
            write(root, name, source)
        result = analyze_project(root)
    nodes = {n["id"]: (n["file"], n["qualified_name"]) for n in result["nodes"]}
    calls = [e for e in result["edges"] if e["type"] == "calls"]
    actual = {(e["evidence"]["file"], e["evidence"]["range"]["start_line"], e["evidence"]["range"]["start_col"], e["expression"]): e for e in calls}
    expected = {(f, line, col, expr): (status, target) for f, line, col, expr, status, target in EXPECTED_CALLS}
    if actual.keys() != expected.keys():
        raise AssertionError(f"Call locations differ: {actual.keys() ^ expected.keys()}")
    predicted = {(*key, nodes[e["target"]]) for key, e in actual.items() if e["resolution_status"] == "resolved"}
    gold = {(*key, target) for key, (_, target) in expected.items() if target is not None}
    tp, fp, fn = len(predicted & gold), len(predicted - gold), len(gold - predicted)
    return {"call_count": len(calls), "true_positive": tp, "false_positive": fp, "false_negative": fn,
            "precision": tp / (tp + fp) if tp + fp else None, "recall": tp / (tp + fn) if tp + fn else None,
            "unresolved_rate": result["stats"]["unresolved_rate"], "parse_failed_file_count": result["stats"]["parse_failed_file_count"],
            "scope": "Seven hand-labeled call sites only; not general project accuracy."}


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
