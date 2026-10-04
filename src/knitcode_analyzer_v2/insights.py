"""Deterministic observations, author documentation, and explicit heuristics."""

from collections import defaultdict, deque
from pathlib import PurePosixPath
import ast

from .models import location

REASONS = {
    "name_not_found": "이름의 내부 대상을 찾지 못했습니다.",
    "parameter_call": "매개변수로 전달되는 실제 함수가 필요합니다.",
    "shadowed_name": "대입·삭제·매개변수 등이 기존 이름을 가립니다.",
    "ambiguous_definition": "중복 또는 조건부 정의로 대상을 하나로 선택할 수 없습니다.",
    "ambiguous_module": "같은 모듈명에 여러 파일이 대응합니다.",
    "dynamic_dispatch": "객체 타입이나 실행 중 값이 필요합니다.",
    "unsupported_syntax": "데코레이터·재수출·closure 등 지원 규칙 밖의 조건입니다.",
    "parse_error": "대상 파일의 파싱에 실패했습니다.",
    "module_not_indexed": "내부 모듈이 제외되었거나 분석 인덱스에 없습니다.",
    "invalid_relative_import": "현재 소스 루트에서 상대 import를 해석할 수 없습니다.",
}


def is_main_guard(node):
    test = node.test if isinstance(node, ast.If) else None
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False
    a, b = test.left, test.comparators[0]
    return ((isinstance(a, ast.Name) and a.id == "__name__" and isinstance(b, ast.Constant) and b.value == "__main__")
            or (isinstance(b, ast.Name) and b.id == "__name__" and isinstance(a, ast.Constant) and a.value == "__main__"))


def build_insights(result, source_files):
    nodes = {n["id"]: n for n in result["nodes"]}
    file_nodes = {n["file"]: n for n in nodes.values() if n["type"] == "file"}
    definitions = defaultdict(list)
    incoming, outgoing = defaultdict(list), defaultdict(list)
    calls_by_file = defaultdict(list)
    file_groups = defaultdict(list)
    for node in nodes.values():
        if node["type"] != "file":
            definitions[node["file"]].append(node)
    for edge in result["edges"]:
        if edge["type"] == "calls":
            calls_by_file[edge["evidence"]["file"]].append(edge)
            outgoing[edge["source"]].append(edge)
            if edge["resolution_status"] == "resolved":
                incoming[edge["target"]].append(edge)
        if edge["type"] in {"calls", "imports"} and edge["resolution_status"] == "resolved":
            a, b = nodes[edge["source"]]["file"], nodes[edge["target"]]["file"]
            if a != b:
                file_groups[a, b, edge["type"]].append(edge["id"])
    metrics = []
    for node in nodes.values():
        if node["type"] == "file":
            continue
        ins, outs = incoming[node["id"]], outgoing[node["id"]]
        metrics.append({"node_id": node["id"], "kind": "observed",
                        "caller_count": len({e["source"] for e in ins if e["source"] != node["id"]}),
                        "callee_count": len({e["target"] for e in outs if e["resolution_status"] == "resolved"}),
                        "call_site_count": len(outs), "incoming_edge_ids": [e["id"] for e in ins],
                        "outgoing_edge_ids": [e["id"] for e in outs]})
    entries = []
    for file in source_files:
        if file.tree is None:
            continue
        guards = [n for n in file.tree.body if is_main_guard(n)]
        if guards or PurePosixPath(file.relative).name == "__main__.py":
            entries.append({"node_id": file_nodes[file.relative]["id"], "kind": "heuristic",
                            "rule": "main_guard" if guards else "main_module",
                            "text": "직접 실행 진입점 후보" if guards else "모듈 실행 진입점 후보",
                            "evidence": {"file": file.relative, "range": location(guards[0]) if guards else file_nodes[file.relative]["range"]}})
    starts = [e["node_id"] for e in entries]
    fallback = not starts
    if fallback:
        ranked = sorted(metrics, key=lambda m: (-m["caller_count"], nodes[m["node_id"]]["file"],
                                                 nodes[m["node_id"]]["range"]["start_line"]))
        starts = [m["node_id"] for m in ranked[:5] if m["caller_count"] > 0]
        if not starts:
            starts = [n["id"] for n in file_nodes.values() if n["range"] is not None][:5]
    queue = deque((n, 0, None, (n,)) for n in starts)
    visited, order, cycles, omitted = set(), [], [], set()
    while queue:
        node_id, depth, via, ancestors = queue.popleft()
        if node_id in visited:
            continue
        visited.add(node_id)
        if len(order) >= 20:
            omitted.add(node_id)
            continue
        node = nodes[node_id]
        order.append({"node_id": node_id, "depth": depth, "via_edge_id": via, "kind": "heuristic",
                      "text": ("연결된 내부 코드" if via else "진입점 후보" if not fallback else "구조를 읽기 위한 대안 시작점"),
                      "evidence": {"file": node["file"], "range": node["range"]}})
        for edge in outgoing[node_id]:
            if edge["resolution_status"] != "resolved" or edge.get("context") in {"annotation", "definition_expression"}:
                continue
            target = edge["target"]
            if target in ancestors:
                cycles.append(edge["id"])
            elif depth < 2:
                queue.append((target, depth + 1, edge["id"], (*ancestors, target)))
            elif target not in visited:
                omitted.add(target)
    components = []
    for file in result["files"]:
        node = file_nodes[file["path"]]
        refs = [n["id"] for n in definitions[file["path"]]]
        related = calls_by_file[file["path"]]
        components.append({"node_id": node["id"], "file": file["path"], "kind": "observed",
                           "text": f"정의 {len(refs)}개 · 호출 위치 {len(related)}개 · 내부 연결 {sum(e['resolution_status'] == 'resolved' for e in related)}개",
                           "definition_ids": refs, "call_edge_ids": [e["id"] for e in related],
                           "evidence": {"file": file["path"], "range": node["range"]},
                           "documentation": {"kind": "documented", "text": node.get("docstring"),
                                             "evidence": {"file": file["path"], "range": node["range"]}} if node.get("docstring") else None})
    return {"overview": {"kind": "observed", "text": f"Python 파일 {len(result['files'])}개와 정의 {len(metrics)}개를 분석했습니다. 업무 목적은 정적 구조만으로 확인할 수 없습니다.",
                         "node_ids": list(file_nodes[f]["id"] for f in file_nodes)},
            "entry_points": entries, "reading_order": order, "reading_limit": {"max_depth": 2, "max_items": 20,
            "omitted_node_count": len(omitted - {o['node_id'] for o in order}), "cycle_edge_ids": sorted(set(cycles))},
            "fallback_used": fallback, "components": components, "metrics": metrics,
            "file_relations": [{"source_file": a, "target_file": b, "type": kind, "count": len(ids), "edge_ids": ids}
                               for (a, b, kind), ids in sorted(file_groups.items())]}

