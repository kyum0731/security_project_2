"""Runtime observations displayed separately from static facts."""

import html


REASONS = {
    "async_or_generator_not_traced": "비동기·제너레이터 실행은 추적 범위 밖",
    "other_thread_not_traced": "추가 스레드에서 실행된 프로젝트 코드 생략",
    "child_process_not_traced": "자식 프로세스 실행 감지: 자식 내부는 추적하지 않음",
    "unmapped_project_code": "프로젝트 경로의 실행 코드가 정적 정의와 매칭되지 않음",
    "event_limit": "이벤트 한도 도달: 이후 실행 기록 생략",
    "source_changed": "분석한 파일이 실행 전후에 변경됨: 저장된 스냅샷 기준 결과",
    "timeout": "시간 제한으로 추적 프로세스 종료",
    "cancelled": "사용자가 실행 취소",
    "collector_error": "추적기 오류로 수집 중단",
    "worker_status_missing": "추적 프로세스의 정상 완료 기록 없음",
    "worker_setup_failed": "실행 준비 실패",
    "incomplete_event_stream": "잘렸거나 유효하지 않은 이벤트 제외",
}


def esc(value):
    return html.escape(str(value), quote=True)


def place(ev):
    r = ev.get("range")
    return ev["file"] + (f":{r['start_line']}:{r['start_col']}–{r['end_line']}:{r['end_col']}" if r else " (정확한 위치 없음)")


def render_runtime_html(result, runtime):
    run, summary = runtime["run"], runtime["summary"]
    nodes = {n["id"]: n for n in result["nodes"]}
    def link(nid):
        n = nodes[nid]
        return f'<a href="#{nid}">{esc(n["file"] + "::" + (n["qualified_name"] or "<module>"))}</a>'
    blocks = [f'<section id="runtime"><h2>실행 관측 결과</h2><p>실행 {esc(run["execution_status"])} · 추적 {esc(run["trace_status"])} · 대상 종료 코드 {esc(run["target_exit_code"])}</p>',
              f'<p class="meta">run: {esc(run["run_id"])} · 전체 경과 {run["elapsed_seconds"]}초 · 기록 이벤트 {summary["event_count"]}개</p>',
              '<p class="notice">이 입력·이 실행에서 관측한 동기 Python 코드입니다. 관측되지 않은 코드는 미사용 코드가 아닙니다. 외부 코드·비동기·다른 스레드·자식 프로세스의 전체 흐름은 포함하지 않습니다. 값은 수집하지 않지만 프로그램 출력 로그에는 값이 포함될 수 있습니다.</p>',
              f'<p>실행 대상: {esc(run["script"] or run["module"])} · 작업 폴더: {esc(run["cwd"])}</p>',
              '<p>원자료: run.json · summary.json · events.jsonl · stdout.log · stderr.log · 실행 무결성: run-manifest.json</p>']
    if run["limitations"]:
        blocks.append('<ul>' + ''.join('<li>' + esc(REASONS.get(r, r)) + '</li>' for r in run["limitations"]) + '</ul>')
    for name, info in run["logs"].items():
        if info.get("truncated") or info.get("read_error"):
            blocks.append(f'<p class="notice">{name} 로그 제한 또는 읽기 오류: {esc(info)}</p>')
    blocks.append('<h3>실행된 코드 요소</h3><ul>')
    for nid, count in summary["node_entries"].items():
        blocks.append(f'<li>{link(nid)} · 진입 {count}회</li>')
    blocks.append('</ul><h3>실행에서 관측한 호출</h3><p class="muted">출발점은 호출 스택상 바로 위 Python 프레임입니다. 중간 C 함수의 콜백·암시적 호출이 있을 수 있습니다. 근거 위치는 상위 프레임의 실행 명령 범위이며 정적 호출 표현식과 항상 일대일로 일치하지 않습니다.</p>')
    for edge in summary["observed_calls"]:
        seqs = edge["event_sequences"]
        shown = ", ".join(map(str, seqs[:50]))
        blocks.append(f'<details id="{edge["id"]}"><summary>{link(edge["source"])} → {link(edge["target"])} · {edge["count"]}회</summary><p>{esc(place(edge["evidence"]))}</p><p>진입 이벤트 번호: {shown}' + (f' · 나머지 {len(seqs)-50}개는 summary.json 확인' if len(seqs)>50 else '') + '</p></details>')
    blocks.append('<h3>이벤트 순서</h3><p class="muted">처음 300개 표시. 전체 순서는 events.jsonl에 있습니다. raise는 처리된 예외도 포함하며 실패 여부는 실행 상태로 확인합니다.</p><div class="table-wrap"><table><tr><th>순번</th><th>이벤트</th><th>코드 / 위치</th></tr>')
    for event in runtime["events"][:300]:
        nid = event.get("node_id")
        content = (link(nid) + ' · ' + esc(place(event["location"]))) if nid in nodes else esc(event.get("reason", ""))
        blocks.append(f'<tr><td>{event["seq"]}</td><td>{esc(event["event"])}<br>{esc(event.get("exception_type", ""))}</td><td>{content}</td></tr>')
    blocks.append('</table></div></section>')
    return "".join(blocks)


def render_runtime_markdown(result, runtime):
    from .ai_markdown import safe
    run, summary = runtime["run"], runtime["summary"]
    nodes = {n["id"]: n for n in result["nodes"]}
    lines = ["", "## 실행 관측 결과", "", f"- run: {run['run_id']}",
             f"- 실행 상태: {run['execution_status']} / 대상 종료 코드: {run['target_exit_code']}",
             f"- 추적 상태: {run['trace_status']} / 기록 이벤트: {summary['event_count']}",
             "", "이 실행에서 관측한 관계입니다. 관측되지 않은 코드는 미사용을 뜻하지 않습니다.", ""]
    for reason in run["limitations"]:
        lines.append("- " + safe(REASONS.get(reason, reason)))
    for edge in summary["observed_calls"]:
        a, b = nodes[edge["source"]], nodes[edge["target"]]
        lines.append(f"- {safe(a['file']+'::'+a['qualified_name'])} → {safe(b['file']+'::'+b['qualified_name'])}: {edge['count']}회 · {safe(place(edge['evidence']))}")
    return "\n".join(lines) + "\n"
