"""Local lexical retrieval and hash-checked source evidence for optional AI."""

import hashlib
import io
from pathlib import Path
import re
import tokenize

from .models import digest

PROMPT_VERSION = "knitcode-evidence-1"


def search(result, query, limit=20):
    if not query.strip() or len(query) > 4000 or not 1 <= limit <= 100:
        raise ValueError("검색어는 1~4000자, limit은 1~100이어야 합니다.")
    words = list(dict.fromkeys(re.findall(r"\w+", query.casefold())))
    if not words:
        raise ValueError("검색어에는 문자 또는 숫자가 필요합니다.")
    hits = []
    for node in result["nodes"]:
        name = (node["qualified_name"] or node["name"]).casefold()
        path, doc = node["file"].casefold(), (node.get("docstring") or "").casefold()
        score = sum(8 * (word == name) + 4 * (word in name) + 2 * (word in path) + (word in doc) for word in words)
        if score:
            hits.append({"node_id": node["id"], "name": node["qualified_name"] or node["name"],
                         "file": node["file"], "type": node["type"], "range": node["range"], "score": score})
    return sorted(hits, key=lambda hit: (-hit["score"], hit["type"] == "file", hit["file"], hit["node_id"]))[:limit]


def read_verified(result, node, files):
    root = Path(result["metadata"]["project_root"]).resolve()
    relative = Path(node["file"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("근거 경로가 프로젝트 범위를 벗어납니다.")
    path = root / relative
    for part in (path, *path.parents):
        if part == root:
            break
        if part.is_symlink() or part.is_junction():
            raise ValueError("근거 경로에 링크가 있습니다. 다시 분석하세요.")
    if not path.resolve().is_relative_to(root):
        raise ValueError("근거 경로가 프로젝트 범위를 벗어납니다.")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != files[node["file"]]["sha256"]:
        raise ValueError("분석 후 원문이 변경되었습니다. 다시 분석하세요: " + node["file"])
    encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
    source = raw.decode(encoding)
    r = node["range"]
    if not r:
        raise ValueError("근거 위치가 없는 파일입니다: " + node["file"])
    # Python source lines use CR/LF, not every Unicode separator in a string literal.
    lines = re.findall(r"[^\r\n]*(?:\r\n|\r|\n|$)", source)
    selected = lines[r["start_line"] - 1:r["end_line"]]
    if not selected:
        return ""
    if len(selected) == 1:
        return selected[0].encode("utf-8")[r["start_col"]:r["end_col"]].decode("utf-8")
    selected[0] = selected[0].encode("utf-8")[r["start_col"]:].decode("utf-8")
    selected[-1] = selected[-1].encode("utf-8")[:r["end_col"]].decode("utf-8")
    return "".join(selected)


def build_context(result, query, *, node_id=None, max_chars=16000, max_nodes=8, depth=1):
    """Budget whole source units; never silently truncate an evidence range."""
    if not 1000 <= max_chars <= 100000 or not 1 <= max_nodes <= 20 or not 0 <= depth <= 2:
        raise ValueError("문맥 범위: max_chars 1000~100000, max_nodes 1~20, depth 0~2")
    if not query.strip() or len(query) > 4000:
        raise ValueError("질문은 1~4000자여야 합니다.")
    nodes = {n["id"]: n for n in result["nodes"]}
    files = {f["path"]: f for f in result["files"]}
    hits = search(result, query)
    if node_id is not None and node_id not in nodes:
        raise ValueError("현재 분석 결과에 없는 node ID입니다.")
    selected = node_id or (hits[0]["node_id"] if hits else None)
    if selected is None:
        raise ValueError("검색 결과가 없습니다. 이름·경로·docstring의 단어로 검색하거나 --node를 지정하세요.")
    distance = {selected: 0}
    for step in range(depth):
        frontier = {nid for nid, d in distance.items() if d == step}
        for edge in result["edges"]:
            if edge["target"] and edge["type"] in {"calls", "imports"}:
                if edge["source"] in frontier:
                    distance.setdefault(edge["target"], step + 1)
                if edge["target"] in frontier:
                    distance.setdefault(edge["source"], step + 1)
    scores = {hit["node_id"]: hit["score"] for hit in hits}
    candidates = sorted(distance, key=lambda nid: (distance[nid], -scores.get(nid, 0), nodes[nid]["file"], nid))
    snippets, omitted, used = [], [], 0
    for nid in candidates:
        node = nodes[nid]
        if len(snippets) >= max_nodes:
            omitted.append({"node_id": nid, "reason": "node_budget"})
            continue
        source = read_verified(result, node, files)
        if len(source) + used > max_chars:
            omitted.append({"node_id": nid, "reason": "source_character_budget", "characters": len(source)})
            continue
        snippets.append({"id": "E" + str(len(snippets) + 1), "node_id": nid, "file": node["file"],
                         "name": node["qualified_name"] or node["name"], "range": node["range"],
                         "file_sha256": files[node["file"]]["sha256"], "distance": distance[nid], "source": source})
        used += len(source)
    included = {s["node_id"] for s in snippets}
    related = [e for e in result["edges"] if e["source"] in included or e["target"] in included]
    context = {"context_version": "1.0", "prompt_version": PROMPT_VERSION,
               "snapshot_id": result["metadata"]["snapshot_id"], "query": query, "selected_node_id": selected,
               "analysis_status": result["metadata"]["analysis_status"],
               "analysis_scope": result["metadata"]["options"],
               "diagnostics": [{"file": d.get("file"), "code": d["code"]} for d in result["diagnostics"]],
               "selection": "explicit_node" if node_id else "lexical_search_top_hit",
               "budget": {"max_source_characters": max_chars, "source_characters": used, "max_nodes": max_nodes, "depth": depth},
               "evidence": snippets,
               "relations": [{key: e.get(key) for key in ("id", "type", "source", "target", "resolution_status", "reason", "evidence")} for e in related[:80]],
               "omitted": omitted, "omitted_relation_count": max(0, len(related) - 80),
               "not_provided": ["프로젝트 전체 원문", "실행 시 값과 실제 호출 대상", "검색·관계 거리 밖의 코드", "Git 이력", "미저장 편집 내용"],
               "limitations": "정적 관계와 제공된 원문만 근거입니다. 문맥 밖의 대상은 이름만으로 확정할 수 없습니다."}
    context["input_hash"] = digest(context)
    return context
