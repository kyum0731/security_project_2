"""A standalone report with native disclosure widgets; no JavaScript or CDN."""

import html
from .common import ANALYSIS_STATUS, CONTEXT, KIND, LIMITATION, STATUS, indexes, label, position, signature, target_text, tree
from ..insights import REASONS


def esc(value):
    return html.escape(str(value), quote=True)


STYLE = """
:root{color-scheme:light;--ink:#17312e;--muted:#536966;--line:#d5e4df;--teal:#146f60;font-family:Segoe UI,Malgun Gothic,system-ui,sans-serif;background:#f1f6f3;color:var(--ink)}
*{box-sizing:border-box}body{margin:0}a{color:#126b63;text-underline-offset:3px;overflow-wrap:anywhere}a:focus-visible,summary:focus-visible{outline:3px solid #dc8c29;outline-offset:4px}
.layout{max-width:1500px;margin:auto;display:grid;grid-template-columns:245px minmax(0,1fr);gap:30px;padding:28px}aside{position:sticky;top:28px;align-self:start;background:#fff;border:1px solid var(--line);border-radius:16px;padding:24px}aside strong{letter-spacing:.13em;font-size:18px}nav{display:grid;gap:17px;margin-top:28px}nav a{text-decoration:none;font-size:14px}.eyebrow{letter-spacing:.16em;text-transform:uppercase;font-size:12px;color:#a3e4cc}
header{background:#123c35;color:#fff;padding:38px;border-radius:20px}h1{font-size:clamp(24px,3vw,38px);line-height:1.3;margin:14px 0}header p{color:#d1e8df}header a{color:#a3e4cc}.meta{font-size:12px;overflow-wrap:anywhere;line-height:1.9;color:var(--muted)}header .meta{color:#b9d4cb}p,li{line-height:1.8}h2{font-size:23px;margin:0 0 18px}h3{font-size:17px}section{background:#fff;border:1px solid var(--line);border-radius:16px;padding:26px;margin:22px 0;scroll-margin-top:20px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:20px 0}.stat{padding:20px;background:#fff;border:1px solid var(--line);border-radius:13px}.stat strong{display:block;font-size:30px;margin-top:10px}.stat span{color:var(--muted);font-size:13px}
.badge{display:inline-block;border-radius:20px;background:#e8f3ee;padding:4px 10px;font-size:12px;color:#245448;margin:3px}.unresolved{background:#fff2d8;color:#825417}.external{background:#eaf0fc;color:#35588e}.builtin{background:#eee9f6;color:#684591}.partial{background:#fff2d8;color:#825417}.empty{background:#eee;color:#555}.notice{border-left:4px solid #d5a34d;background:#fffaee;padding:14px 18px;font-size:14px}.muted{color:var(--muted);font-size:14px}.tree{font:13px/1.9 Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f8f6;padding:20px;border-radius:10px}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;vertical-align:top;padding:12px 9px;border-bottom:1px solid var(--line);overflow-wrap:anywhere}th{background:#f5f8f6;white-space:nowrap}td code{white-space:pre-wrap}code{font:12px/1.7 Consolas,monospace;overflow-wrap:anywhere}.code-node{border-top:1px solid var(--line);margin-top:22px;padding-top:18px;scroll-margin-top:20px}.docstring{white-space:pre-wrap;background:#f5f8f6;border-left:3px solid #84b6a5;padding:14px;font-size:13px;overflow-wrap:anywhere}details{margin:12px 0}summary{cursor:pointer;padding:12px 0;font-weight:600;overflow-wrap:anywhere}.file{border:1px solid var(--line);padding:8px 18px;border-radius:12px}.read-step{padding:12px 0;border-bottom:1px solid var(--line)}.read-step p{margin:5px 0}.small{font-size:12px}footer{padding:12px 0 28px;color:var(--muted);font-size:12px;overflow-wrap:anywhere}
@media(max-width:850px){.layout{display:block;padding:14px}aside{position:static;margin-bottom:18px;padding:20px}nav{display:flex;flex-wrap:wrap;gap:14px;margin-top:16px}header{padding:26px}.stats{grid-template-columns:repeat(2,1fr)}section{padding:18px}}
@media print{.layout{display:block;padding:0}aside{display:none}header{background:white;color:var(--ink);border:1px solid var(--line)}header p,header .meta{color:var(--muted)}details::details-content{display:block}section{break-inside:auto}.stats{grid-template-columns:repeat(4,1fr)}}
"""


def render_html(result):
    m, s, insights = result["metadata"], result["stats"], result["insights"]
    nodes, file_nodes, incoming, outgoing, imports = indexes(result)
    edge_by_id = {e["id"]: e for e in result["edges"]}
    def link(node_id):
        return f'<a href="#{node_id}">{esc(label(nodes[node_id]))}</a>'
    def evidence(ev):
        return f'<span class="meta">{esc(position(ev))}</span>'
    def edge_row(edge):
        status = edge["resolution_status"]
        target = link(edge["target"]) if edge["target"] else esc(target_text(edge, nodes))
        context = f'<br><span class="meta">{esc(CONTEXT[edge["context"]])}</span>' if "context" in edge else ""
        return (f'<tr id="{edge["id"]}"><td><code>{esc(edge["expression"])}</code>{context}</td>'
                f'<td><span class="badge {status}">{STATUS[status]}</span><br>{target}</td><td>{evidence(edge["evidence"])}</td></tr>')
    def edge_table(edges):
        return '<div class="table-wrap"><table><thead><tr><th>소스 표현식</th><th>대상 / 해석 상태</th><th>근거 위치</th></tr></thead><tbody>' + "".join(edge_row(e) for e in edges) + '</tbody></table></div>'
    blocks = []
    blocks.append('<section id="overview"><h2>프로젝트 한눈에 보기</h2><p>' + esc(insights["overview"]["text"]) + '</p><p>' +
                  " ".join(f'<span class="badge {k}">{STATUS[k]} {v}</span>' for k, v in s["calls_by_status"].items()) +
                  f'</p><p class="notice">{LIMITATION}</p><p class="muted">분석 범위: {esc(m["source_root"])} · {"프로젝트 전체의 제외되지 않은 Python 파일" if m["source_root"] == "." else "선택한 소스 루트 안의 Python 파일만 분석"}<br>외부 패키지의 설치·출처를 확인하지 않았습니다. 연결률은 정확도가 아닙니다.</p></section>')
    reading = '<section id="reading"><h2>먼저 살펴볼 곳</h2><p class="muted">규칙에 따른 읽기 안내입니다. 실제 실행 순서도가 아닙니다.</p>'
    if insights["fallback_used"]:
        reading += '<p class="notice">진입점 후보를 찾지 못했습니다. 라이브러리에는 단일 진입점이 없을 수 있습니다. 구조를 읽기 위한 대안을 표시합니다.</p>'
    for entry in insights["entry_points"][:20]:
        reading += f'<p><span class="badge">후보 · {entry["rule"]}</span> {link(entry["node_id"])}<br>{evidence(entry["evidence"])}</p>'
    if len(insights["entry_points"]) > 20:
        reading += f'<p>진입점 후보 {len(insights["entry_points"])}개 중 20개 표시. 전체는 analysis.json에서 확인할 수 있습니다.</p>'
    for item in insights["reading_order"]:
        via = edge_by_id.get(item["via_edge_id"])
        reading += f'<div class="read-step"><span class="badge">깊이 {item["depth"]}</span> {link(item["node_id"])}<p class="small">{esc(item["text"])} · {evidence(item["evidence"])}</p>'
        if via:
            reading += f'<p class="small">호출 근거: <a href="#{via["id"]}">{esc(position(via["evidence"]))}</a></p>'
        reading += '</div>'
    lim = insights["reading_limit"]
    reading += f'<p class="meta">깊이 2 / 최대 20개 · 추가 대상 생략 {lim["omitted_node_count"]}개 · 순환 연결 {len(lim["cycle_edge_ids"])}개</p></section>'
    blocks.append(reading)
    blocks.append(f'<section id="tree"><h2>파일 구조</h2><pre class="tree">{esc(tree(result["files"]))}</pre></section>')
    relations = '<section id="relations"><h2>파일 사이 관계</h2><p class="muted">방향은 호출·import를 하는 파일 → 대상 파일입니다. 집계는 원래 근거를 보존합니다.</p>'
    if not insights["file_relations"]:
        relations += '<p>분석된 내부 파일 간 연결이 없습니다.</p>'
    for rel in insights["file_relations"]:
        relations += f'<details><summary>{esc(rel["source_file"])} → {esc(rel["target_file"])} <span class="badge">{rel["type"]} {rel["count"]}</span></summary><ul>'
        relations += "".join(f'<li><a href="#{eid}">{esc(position(edge_by_id[eid]["evidence"]))}</a></li>' for eid in rel["edge_ids"])
        relations += '</ul></details>'
    blocks.append(relations + '</section>')
    metrics = {v["node_id"]: v for v in insights["metrics"]}
    components = {c["file"]: c for c in insights["components"]}
    detail = '<section id="files"><h2>파일·코드 상세</h2><p class="muted">파일을 펼쳐 정의와 호출 근거를 확인하세요. 위치는 행 1부터, 열 0부터의 UTF-8 바이트이며 끝은 제외합니다.</p>'
    for file in result["files"]:
        detail += f'<details class="file"><summary>{esc(file["path"])} <span class="badge">{file["parse_status"]}</span></summary><p class="muted">{esc(components[file["path"]]["text"])}</p>'
        if imports[file["path"]]:
            detail += '<h3>import</h3>' + edge_table(imports[file["path"]])
        for node in file_nodes[file["path"]]:
            detail += f'<article class="code-node" id="{node["id"]}"><h3><span class="badge">{KIND[node["type"]]}</span> {esc(signature(node))}</h3>' + evidence({"file": node["file"], "range": node["range"]})
            if node.get("docstring"):
                detail += f'<details><summary>작성자 docstring · 실제 동작 보장은 아님</summary><div class="docstring">{esc(node["docstring"])}</div></details>'
            if node["id"] in metrics:
                metric = metrics[node["id"]]
                detail += f'<p class="meta">고유 호출자 {metric["caller_count"]} · 내부 호출 대상 {metric["callee_count"]} · 호출 위치 {metric["call_site_count"]}</p>'
            detail += '<h3>호출자</h3>'
            if incoming[node["id"]]:
                detail += '<ul>' + "".join(f'<li>{link(e["source"])} · <a href="#{e["id"]}">{esc(position(e["evidence"]))}</a></li>' for e in incoming[node["id"]]) + '</ul>'
            else:
                detail += '<p class="muted">분석된 내부 호출자 없음 · 미사용을 뜻하지 않습니다.</p>'
            detail += '<h3>호출 대상</h3>' + (edge_table(outgoing[node["id"]]) if outgoing[node["id"]] else '<p class="muted">이 범위에 수집된 호출 없음</p>') + '</article>'
        detail += '</details>'
    blocks.append(detail + '</section>')
    diag = '<section id="diagnostics"><h2>분석 한계와 진단</h2><p class="muted">스코프별 해석 규칙에 기반한 결과입니다. 객체 타입·상속·재수출·동적 import·실행 경로는 완전히 해석하지 않습니다.</p><ul>'
    diag += "".join(f'<li><b>{esc(reason)} · {count}개</b> — {esc(REASONS.get(reason, reason))}</li>' for reason, count in s["unresolved_by_reason"].items())
    diag += '</ul>'
    if result["diagnostics"]:
        diag += '<ul>' + "".join(f'<li><span class="badge">{d["severity"]}</span> {esc(d.get("file") or "프로젝트")} · {esc(d["code"])}<br>{esc(d["message"])}</li>' for d in result["diagnostics"]) + '</ul>'
    else:
        diag += '<p>기록된 파일·탐색 진단이 없습니다.</p>'
    diag += '<details><summary>제외·생략한 항목</summary><p class="muted">제외 디렉터리 안의 파일 수는 추정하지 않습니다.</p><ul>'
    diag += "".join(f'<li>{esc(i["path"])} · {i["kind"]} · {i["reason"]}</li>' for i in m["coverage"]["skipped"])
    blocks.append(diag + '</ul></details></section>')
    cards = "".join(f'<div class="stat"><span>{name}</span><strong>{value}</strong></div>' for name, value in (
        ("Python 파일", s["file_count"]), ("정의", s["definition_count"]), ("호출 위치", s["call_count"]), ("파싱 실패", s["parse_failed_file_count"])))
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
            f'<title>KnitCode · 프로젝트 분석</title><style>{STYLE}</style></head><body><div class="layout"><aside><strong>KNITCODE</strong>'
            '<p class="muted">구조를 읽는 첫 지도</p><nav><a href="#overview">01 · 한눈에 보기</a><a href="#reading">02 · 읽기 시작점</a><a href="#tree">03 · 파일 구조</a><a href="#relations">04 · 파일 간 관계</a><a href="#files">05 · 코드 상세</a><a href="#diagnostics">06 · 진단과 한계</a></nav></aside><main>'
            f'<header><div class="eyebrow">Local Python Analysis / No AI</div><h1>낯선 코드에서<br>읽기 시작점을 찾으세요.</h1><p>{esc(m["project_root"])}</p><span class="badge {m["analysis_status"]}">{ANALYSIS_STATUS[m["analysis_status"]]}</span>'
            f'<div class="meta">소스 루트: {esc(m["source_root"])} · Python {m["python_version"]}<br>분석 시각(UTC): {m["analyzed_at"]}</div></header><div class="stats">{cards}</div>'
            + "".join(blocks) + f'<footer>snapshot: {m["snapshot_id"]}<br>분석기 {m["analyzer_version"]} · 스키마 {result["schema_version"]} · 소요 {s["analysis_seconds"]}초<br>원자료: analysis.json · 문서: report.md · 저장 무결성: manifest.json</footer></main></div></body></html>')
