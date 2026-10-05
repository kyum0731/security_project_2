from collections import defaultdict
from ..insights import REASONS

STATUS = {"resolved": "내부 연결", "builtin": "내장 이름", "external": "범위 밖 import", "unresolved": "미해결"}
ANALYSIS_STATUS = {"complete": "분석 완료", "partial": "부분 분석", "empty": "Python 파일 없음"}
KIND = {"file": "파일", "function": "함수", "method": "메서드", "class": "클래스", "variable": "변수"}
RELATION = {"contains": "소속", "calls": "호출", "imports": "가져오기", "reads": "읽기",
            "writes": "이름 쓰기", "deletes": "이름 삭제", "references": "참조", "inherits": "상속",
            "depends_on": "대입식 참조"}
CONTEXT = {"module_body": "모듈 본문", "class_body": "클래스 본문", "function_body": "함수 본문",
           "annotation": "타입 힌트 · 실행 여부 미확정", "definition_expression": "정의 시 표현식"}
LIMITATION = "정적 관계는 실제 실행 순서·횟수나 모든 호출 대상을 보장하지 않습니다. 미해결은 코드 오류나 취약점 판정이 아닙니다."


def label(node):
    return f"{node['file']}::{node['qualified_name']}" if node["qualified_name"] else node["file"]


def position(evidence):
    r = evidence.get("range")
    return f"{evidence['file']}:{r['start_line']}:{r['start_col']}–{r['end_line']}:{r['end_col']}" if r else f"{evidence['file']} (위치 없음)"


def target_text(edge, nodes):
    if edge["target"]:
        return label(nodes[edge["target"]])
    if edge["resolution_status"] == "builtin":
        return edge["builtin_name"] + " (사용자 이름 가림 없음)"
    if edge["resolution_status"] == "external":
        return edge["external_name"] + " (설치·외부 패키지 여부 미확인)"
    return REASONS.get(edge.get("reason"), edge.get("reason") or "알 수 없음")


def signature(node):
    if node["type"] not in {"function", "method"}:
        return node["name"]
    params = node.get("parameters", [])
    parts = []
    for i, p in enumerate(params):
        if p["kind"] == "keyword_only" and not any(v["kind"] == "var_positional" for v in params[:i]) and (i == 0 or params[i-1]["kind"] != "keyword_only"):
            parts.append("*")
        prefix = "**" if p["kind"] == "var_keyword" else "*" if p["kind"] == "var_positional" else ""
        parts.append(prefix + p["name"] + (f": {p['annotation']}" if p["annotation"] else "") +
                     (f" = {p['default']}" if p["default"] is not None else ""))
        if p["kind"] == "positional_only" and (i == len(params)-1 or params[i+1]["kind"] != "positional_only"):
            parts.append("/")
    return ("async " if node.get("is_async") else "") + node["name"] + "(" + ", ".join(parts) + ")" + (f" -> {node['returns']}" if node.get("returns") else "")


def tree(files):
    root = {}
    statuses = {f["path"]: f["parse_status"] for f in files}
    for file in files:
        cursor = root
        for part in file["path"].split("/"):
            cursor = cursor.setdefault(part, {})
    lines = []
    def walk(items, prefix="", path=""):
        for i, (name, children) in enumerate(sorted(items.items())):
            last = i == len(items)-1
            current = path + name
            status = statuses.get(current)
            lines.append(prefix + ("└─ " if last else "├─ ") + name + ("/" if children else "") +
                         (f" [{status}]" if status and status != "ok" else ""))
            if children:
                walk(children, prefix + ("   " if last else "│  "), current + "/")
    walk(root)
    return "\n".join(lines) or "(분석한 Python 파일 없음)"


def indexes(result):
    nodes = {n["id"]: n for n in result["nodes"]}
    file_nodes, incoming, outgoing, imports = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
    for node in result["nodes"]:
        file_nodes[node["file"]].append(node)
    for edge in result["edges"]:
        if edge["type"] == "calls":
            outgoing[edge["source"]].append(edge)
            if edge["target"]:
                incoming[edge["target"]].append(edge)
        if edge["type"] == "imports":
            imports[edge["evidence"]["file"]].append(edge)
    return nodes, file_nodes, incoming, outgoing, imports
