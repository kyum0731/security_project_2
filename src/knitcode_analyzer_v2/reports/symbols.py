"""Symbol-level evidence tables and a bounded Markdown diagram."""

import html

from .common import KIND, RELATION, label, position

EXPLANATION = ("변수는 모듈 변수·지역 변수·매개변수·클래스 본문의 속성을 스코프별로 구분합니다. "
               "읽기·이름 쓰기·삭제는 구문상 관계이며 값 전달이나 실행 성공을 보장하지 않습니다. "
               "소속은 소유 범위 → 코드 요소, 읽기·쓰기는 사용 범위 → 변수, 상속은 자식 → 부모 방향입니다. "
               "대입식 참조는 대입받는 변수 → 우변에서 사용하는 변수이며 런타임 값의 흐름을 증명하지 않습니다. "
               "self.x 등 객체 속성, 별칭을 통한 값 추적, 람다·컴프리헨션 내부 변수 관계는 아직 지원하지 않습니다.")


def render_symbol_html(result):
    esc = lambda value: html.escape(str(value), quote=True)
    nodes = {n["id"]: n for n in result["nodes"]}
    def link(nid):
        return f'<a href="#{nid}">{esc(label(nodes[nid]))}</a>'
    rows = []
    for edge in result["edges"]:
        if edge["type"] in {"calls", "imports"}:
            continue  # Their canonical evidence anchors are in code detail.
        target = link(edge["target"]) if edge["target"] else '미해결 · ' + esc(edge.get("reason"))
        rows.append(f'<tr id="{edge["id"]}"><td>{link(edge["source"])}</td>'
                    f'<td>{RELATION[edge["type"]]}</td><td>{target}</td>'
                    f'<td>{esc(position(edge["evidence"]))}<br><code>{esc(edge.get("expression", ""))}</code></td></tr>')
    return ('<section id="symbol-relations"><h2>함수·클래스·변수 관계</h2>'
            f'<p>{esc(EXPLANATION)}</p><p>변수 {result["stats"]["variable_count"]}개. '
            '호출·import 근거는 코드 상세, 나머지 관계는 아래 표에서 확인할 수 있습니다.</p>'
            '<details><summary>소속·변수 사용·참조·상속 근거 전체 펼치기</summary>'
            '<div class="table-wrap"><table><thead><tr><th>출발 요소</th><th>관계</th><th>대상 요소</th><th>근거</th></tr></thead>'
            '<tbody>' + ''.join(rows) + '</tbody></table></div></details></section>')


def render_symbol_markdown(result):
    from .markdown import esc
    nodes = {n["id"]: n for n in result["nodes"]}
    edges = [e for e in result["edges"] if e["target"]]
    # Prefer semantic relations; containment fills the remaining diagram budget.
    edges.sort(key=lambda e: (e["type"] == "contains", e["id"]))
    selected, ids = [], {}
    for edge in edges:
        added = set((edge["source"], edge["target"])) - ids.keys()
        if len(ids) + len(added) > 40 or len(selected) >= 80:
            continue
        for nid in (edge["source"], edge["target"]):
            ids.setdefault(nid, f'n{len(ids)}')
        selected.append(edge)
    lines = ["## 함수·클래스·변수 관계", "", EXPLANATION, "",
             f"변수 {result['stats']['variable_count']}개. 아래 그림은 노드 최대 40개 / 관계 최대 80개입니다. "
             f"전체 노드 {len(nodes)}개 중 {len(ids)}개, 연결된 관계 {len(edges)}개 중 {len(selected)}개 표시합니다. "
             "전체 탐색은 report.html, 원자료는 analysis.json을 이용하세요.", "",
             "Mermaid를 지원하는 Markdown 뷰어에서 그림으로 표시됩니다.", "", "```mermaid", "flowchart LR"]
    for nid, short in ids.items():
        # Code-derived labels cannot terminate a fence or inject Mermaid syntax.
        raw = KIND[nodes[nid]["type"]] + " " + label(nodes[nid])
        safe = ''.join(ch if ch.isalnum() or ch in ' ._/' else ' ' for ch in raw)[:100]
        lines.append(f'  {short}["{safe}"]')
    lines.extend(f'  {ids[e["source"]]} -->|{e["type"]}| {ids[e["target"]]}' for e in selected)
    lines += ["```", "", "### 소속·변수 사용·참조·상속 근거", "",
              "| 출발 요소 | 관계 | 대상 요소 | 근거 위치 / ID |", "| --- | --- | --- | --- |"]
    for edge in result["edges"]:
        if edge["type"] in {"calls", "imports"}:
            continue
        target = label(nodes[edge["target"]]) if edge["target"] else "미해결: " + str(edge.get("reason"))
        lines.append(f'| {esc(label(nodes[edge["source"]]))} | {RELATION[edge["type"]]} | {esc(target)} | '
                     f'{esc(position(edge["evidence"]))} / {edge["id"]} |')
    return "\n".join(lines)
