"""Readable AI output with escaped model text, evidence and explicit limitations."""

import html
import re


def safe(value):
    value = html.escape(str(value), quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", value).replace("\n", " ")


def render_ai_markdown(result):
    context = result["context"]
    lines = ["# KnitCode AI 설명", "", f"- 상태: {safe(result['status'])}",
             f"- 질문: {safe(context['query'])}", f"- 연결: {safe(result.get('provider', ''))}",
             f"- 모델: {safe(result['model'])}", f"- 서버: {safe(result['endpoint'])}",
             f"- snapshot: {safe(result['snapshot_id'])}", f"- 입력 해시: {safe(result['input_hash'])}",
             "", "> AI 설명입니다. 근거의 존재·위치 확인은 설명의 정확성 보장이 아닙니다.", ""]
    if result["status"] == "failed":
        lines += ["## 설명 생성 실패", "", safe(result["error"]), "", "정적 분석 보고서는 그대로 사용할 수 있습니다.", ""]
    else:
        answer = result["answer"]
        lines += ["## 설명", ""]
        for item in answer["claims"]:
            kind = "관찰" if item["kind"] == "observation" else "추정"
            lines += [f"- **{kind}**: {safe(item['text'])} (근거: {', '.join(item['evidence_ids'])})"]
        lines += ["", "## AI가 밝힌 한계", ""]
        lines += ["- " + safe(value) for value in answer["limitations"]] or ["- 별도 한계 설명 없음"]
        lines += ["", "## AI 관계 제안 — 미검증", ""]
        for relation in answer["suggested_relations"]:
            lines += [f"- {safe(relation['source'])} → {safe(relation['target'])} ({safe(relation['type'])}): {safe(relation['explanation'])} (근거: {', '.join(relation['evidence_ids'])})"]
        if not answer["suggested_relations"]:
            lines += ["제안 없음"]
        lines += ["", "제안은 정적 관계·그래프에 자동 반영되지 않습니다.", ""]
    lines += ["## 제공한 근거 원문", ""]
    for item in context["evidence"]:
        r = item["range"]
        lines += [f"### {item['id']} · {safe(item['file'])}", "",
                  f"{safe(item['name'])} · {r['start_line']}:{r['start_col']}–{r['end_line']}:{r['end_col']} (행 1 기준·UTF-8 바이트 열 0 기준·끝 제외)", ""]
        fence = "`" * max(3, max((len(s) for s in re.findall(r"`+", item["source"])), default=0) + 1)
        lines += [fence + "python", item["source"], fence, ""]
    lines += ["## 제공하지 않은 범위", ""]
    lines += ["- " + safe(item) for item in context["not_provided"]]
    lines += [f"- 예산으로 생략한 원문: {len(context['omitted'])}개", f"- 생략한 관계: {context['omitted_relation_count']}개", ""]
    for item in context["omitted"]:
        lines += [f"- {safe(item['node_id'])}: {safe(item['reason'])}"]
    return "\n".join(lines) + "\n"
