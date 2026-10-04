"""Public, read-only pipeline. Presentation and persistence are separate."""

import ast
import hashlib
import platform
from collections import Counter
from datetime import datetime, timezone
from time import perf_counter

from .models import AnalysisResult, Collection, SCHEMA_VERSION, VERSION, digest
from .parser import parse_file
from .resolver import Resolver
from .scanner import EXCLUDED, scan_project
from .symbols import SymbolCollector
from .insights import build_insights


def normalize(collection):
    ids = {n["id"]: "node:" + digest([n["type"], n["file"], n["qualified_name"],
                                   (n["range"] or {}).get("start_line"), (n["range"] or {}).get("start_col")])
           for n in collection.nodes}
    for node in collection.nodes:
        node["id"] = ids[node["id"]]
        node["parent"] = ids[node["parent"]] if node["parent"] else None
    for edge in collection.edges:
        edge["source"] = ids[edge["source"]]
        edge["target"] = ids[edge["target"]] if edge["target"] else None
        ev = edge["evidence"]
        edge["evidence"] = {"file": ev["file"], "range": {"start_line": ev["line"], "start_col": ev["col"],
                                                              "end_line": ev["end_line"], "end_col": ev["end_col"]}}
        edge.pop("analyzer", None)
        if edge["type"] == "contains":
            edge.pop("resolution_status", None)
            rule = "lexical_containment"
        else:
            edge.setdefault("reason", None)
            rule = edge.pop("resolution_rule", "conservative_name_resolution")
        edge["provenance"] = {"provider": "python_ast", "resolution_rule": rule}
        edge["id"] = "edge:" + digest(edge)
    collection.nodes.sort(key=lambda n: (n["file"], (n["range"] or {}).get("start_line", 0),
                                         (n["range"] or {}).get("start_col", 0), n["id"]))
    collection.edges.sort(key=lambda e: (e["evidence"]["file"], e["evidence"]["range"]["start_line"],
                                         e["evidence"]["range"]["start_col"], e["type"], e["id"]))
    return ids


def validate_result(result):
    """Cross-reference and count checks, in addition to the published JSON schema."""
    if result["schema_version"] != SCHEMA_VERSION:
        raise ValueError("지원하지 않는 분석 스키마입니다.")
    nodes = {n["id"]: n for n in result["nodes"]}
    files = {f["path"]: f for f in result["files"]}
    if len(nodes) != len(result["nodes"]):
        raise ValueError("중복 노드 ID")
    edge_ids = set()
    parents = Counter()
    for edge in result["edges"]:
        if edge["id"] in edge_ids or edge["source"] not in nodes:
            raise ValueError("관계 ID 또는 source 무결성 오류")
        edge_ids.add(edge["id"])
        needs_target = edge["type"] == "contains" or edge.get("resolution_status") == "resolved"
        if (needs_target and edge["target"] not in nodes) or (not needs_target and edge["target"] is not None):
            raise ValueError("관계 target 무결성 오류")
        if edge["type"] == "contains" and nodes[edge["target"]]["parent"] != edge["source"]:
            raise ValueError("소속 관계 불일치")
        if edge["type"] == "contains":
            parents[edge["target"]] += 1
        r = edge["evidence"]["range"]
        if (r["start_line"], r["start_col"]) > (r["end_line"], r["end_col"]):
            raise ValueError("잘못된 근거 범위")
        ev_file = edge["evidence"]["file"]
        if ev_file not in files or nodes[edge["source"]]["file"] != ev_file:
            raise ValueError("근거 파일 불일치")
        file_range = nodes[files[ev_file]["node_id"]]["range"]
        if file_range is None or (r["end_line"], r["end_col"]) > (file_range["end_line"], file_range["end_col"]):
            raise ValueError("파일 밖 근거 범위")
    statuses = Counter(e["resolution_status"] for e in result["edges"] if e["type"] == "calls")
    if sum(statuses.values()) != result["stats"]["call_count"]:
        raise ValueError("호출 통계 불일치")
    if any(statuses[s] != c for s, c in result["stats"]["calls_by_status"].items()):
        raise ValueError("상태 통계 불일치")
    for node in nodes.values():
        if node["parent"] is not None and node["parent"] not in nodes:
            raise ValueError("부모 노드 누락")
        if node["type"] != "file" and parents[node["id"]] != 1:
            raise ValueError("정의의 소속 관계 누락 또는 중복")
        if node["file"] not in files:
            raise ValueError("노드의 소속 파일 누락")
    for file in files.values():
        if file["node_id"] not in nodes or nodes[file["node_id"]]["file"] != file["path"] or nodes[file["node_id"]]["type"] != "file":
            raise ValueError("파일 노드 불일치")
    stats = result["stats"]
    if (stats["file_count"] != len(files) or stats["parsed_file_count"] != sum(f["parse_status"] == "ok" for f in files.values())
            or stats["parsed_file_count"] + stats["parse_failed_file_count"] != len(files)
            or stats["definition_count"] != sum(n["type"] != "file" for n in nodes.values())
            or stats["import_count"] != sum(e["type"] == "imports" for e in result["edges"])):
        raise ValueError("파일·정의·import 통계 불일치")
    insights = result.get("insights", {})
    for group in ("entry_points", "reading_order", "components", "metrics"):
        for item in insights.get(group, []):
            if item["node_id"] not in nodes:
                raise ValueError("설명의 근거 노드 누락")
            if item.get("via_edge_id") and item["via_edge_id"] not in edge_ids:
                raise ValueError("읽기 안내의 호출 근거 누락")
            for key in ("call_edge_ids", "incoming_edge_ids", "outgoing_edge_ids"):
                if not set(item.get(key, [])) <= edge_ids:
                    raise ValueError("설명의 근거 관계 누락")
    for rel in insights.get("file_relations", []):
        if not set(rel["edge_ids"]) <= edge_ids or rel["count"] != len(rel["edge_ids"]):
            raise ValueError("파일 관계 집계 불일치")


def analyze_project(project_root, *, source_root=None, excludes=(), excluded_paths=()) -> AnalysisResult:
    started = perf_counter()
    excludes = tuple(sorted(set(excludes)))
    scan = scan_project(project_root, source_root, excludes, excluded_paths)
    collection = Collection()
    diagnostics = scan.diagnostics
    for file in scan.files:
        diagnostic = parse_file(file)
        if diagnostic:
            diagnostics.append(diagnostic)
        local = Collection()
        try:
            SymbolCollector(file, local).collect()
        except RecursionError:
            file.tree, file.parse_status = None, "parser_error"
            local = Collection()
            SymbolCollector(file, local).collect()
            diagnostics.append({"file": file.relative, "code": "parser_error", "severity": "error",
                                "message": "구조 수집 중 재귀 한도를 초과했습니다."})
        for attr in ("nodes", "edges", "imports", "calls"):
            getattr(collection, attr).extend(getattr(local, attr))
    Resolver(scan.files, scan.blocked_modules).resolve(collection)
    ids = normalize(collection)
    for file in scan.files:
        if not file.content_hash:
            continue
        try:
            changed = hashlib.sha256(file.path.read_bytes()).hexdigest() != file.content_hash
        except OSError:
            changed = True
        if changed:
            diagnostics.append({"file": file.relative, "code": "source_changed", "severity": "error",
                                "message": "분석 중 파일이 변경되었습니다. 다시 분석하세요."})
    for edge in collection.edges:
        if edge["type"] == "imports" and edge["resolution_status"] == "unresolved":
            diagnostics.append({**edge["evidence"], "code": "unresolved_import", "severity": "warning",
                                "reason": edge["reason"], "message": edge["expression"]})
    if scan.source == scan.project and (scan.project / "src").is_dir():
        diagnostics.append({"file": None, "code": "source_root_hint", "severity": "info",
                            "message": "src 레이아웃이면 --source-root src를 검토하세요. 이 옵션은 src 밖 파일을 분석하지 않습니다."})
    files = [{"path": f.relative, "module": f.module, "sha256": f.content_hash,
              "encoding": f.encoding, "parse_status": f.parse_status, "node_id": ids[f.node_id]} for f in scan.files]
    status = "partial" if any(d["severity"] == "error" for d in diagnostics) else "complete" if files else "empty"
    options = {"source_root": scan.source.relative_to(scan.project).as_posix(), "excludes": list(excludes),
               "excluded_directories": sorted(EXCLUDED), "follow_links": False}
    calls = [e for e in collection.edges if e["type"] == "calls"]
    statuses = Counter(e["resolution_status"] for e in calls)
    reasons = Counter(e["reason"] for e in calls if e["resolution_status"] == "unresolved")
    result = AnalysisResult({
        "schema_version": SCHEMA_VERSION,
        "metadata": {"analyzer": "knitcode_analyzer_v2", "analyzer_version": VERSION,
                     "python_version": platform.python_version(), "project_root": scan.project.as_posix(),
                     "source_root": options["source_root"], "analyzed_at": datetime.now(timezone.utc).isoformat(),
                     "analysis_status": status, "options": options,
                     "positions": {"line_base": 1, "column_base": 0, "column_unit": "utf-8-bytes", "end_exclusive": True},
                     "snapshot_id": digest([VERSION, SCHEMA_VERSION, platform.python_version(), options, files, status,
                                            collection.nodes, collection.edges]),
                     "coverage": {"skipped": scan.skipped, "scope": "whole_project" if scan.source == scan.project else "source_root_only"}},
        "files": files, "nodes": collection.nodes, "edges": collection.edges,
        "diagnostics": sorted(diagnostics, key=lambda d: (d.get("file") or "", d.get("range", {}).get("start_line", 0), d["code"])),
        "stats": {"file_count": len(files), "read_file_count": sum(f.content_hash is not None for f in scan.files),
                  "parsed_file_count": sum(f.parse_status == "ok" for f in scan.files),
                  "parse_failed_file_count": sum(f.parse_status != "ok" for f in scan.files),
                  "skipped_file_count": sum(s["kind"] == "file" for s in scan.skipped),
                  "skipped_directory_count": sum(s["kind"] == "directory" for s in scan.skipped),
                  "definition_count": sum(n["type"] != "file" for n in collection.nodes),
                  "import_count": len(collection.imports), "call_count": len(calls),
                  "calls_by_status": {s: statuses[s] for s in ("resolved", "builtin", "external", "unresolved")},
                  "unresolved_by_reason": dict(sorted(reasons.items())),
                  "resolution_rate": statuses["resolved"] / len(calls) if calls else None,
                  "unresolved_rate": statuses["unresolved"] / len(calls) if calls else None,
                  "analysis_seconds": 0.0},
    })
    result["insights"] = build_insights(result, scan.files)
    result["stats"]["analysis_seconds"] = round(perf_counter() - started, 6)
    validate_result(result)
    return result
