"""Separate opt-in search/context/explain CLI. Static reports stay untouched."""

import argparse
import os
from pathlib import Path
import sys

from .analyzer import analyze_project
from .context import build_context, search
from .exporter import to_json


def main(argv=None):
    parser = argparse.ArgumentParser(description="로컬 검색·근거 문맥 구성·선택 AI 설명. explain만 설정한 서버로 질문과 코드 문맥을 전송합니다.")
    parser.add_argument("action", choices=("search", "context", "explain"))
    parser.add_argument("project", help="분석할 로컬 프로젝트")
    parser.add_argument("--query", required=True, help="이름·경로·docstring 검색어 또는 설명할 질문")
    parser.add_argument("--source-root")
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--node", help="context/explain의 명시적 대상 node ID (search 결과에서 확인)")
    parser.add_argument("--max-chars", type=int, default=16000, help="제공할 원문 문자 수 예산. 토큰 수가 아님")
    parser.add_argument("--max-nodes", type=int, default=8)
    parser.add_argument("--depth", type=int, default=1, help="호출·import 주변 거리 0~2")
    parser.add_argument("--output", help="새 JSON 파일에 저장. 생략하면 stdout. 기존 파일은 덮어쓰지 않음")
    parser.add_argument("--base-url", default=os.environ.get("KNITCODE_AI_BASE_URL"), help="예: https://서버/v1 또는 http://localhost:포트/v1")
    parser.add_argument("--model", default=os.environ.get("KNITCODE_AI_MODEL"))
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        output = Path(args.output).expanduser() if args.output else None
        if output and (output.exists() or output.is_symlink() or output.suffix.lower() != ".json"):
            raise ValueError("--output에는 존재하지 않는 새 .json 파일을 지정하세요.")
        if args.action == "explain" and (not args.base_url or not args.model):
            raise ValueError("AI에는 --base-url/--model 또는 KNITCODE_AI_BASE_URL/KNITCODE_AI_MODEL 설정이 필요합니다.")
        result = analyze_project(args.project, source_root=args.source_root, excludes=args.exclude)
        status = 0
        if args.action == "search":
            value = {"snapshot_id": result["metadata"]["snapshot_id"], "analysis_status": result["metadata"]["analysis_status"],
                     "query": args.query, "matches": search(result, args.query)}
        else:
            value = build_context(result, args.query, node_id=args.node, max_chars=args.max_chars, max_nodes=args.max_nodes, depth=args.depth)
            if args.action == "explain":
                from .ai import AIError, endpoint_url, explain
                endpoint, _ = endpoint_url(args.base_url)
                print(f"AI 전송 대상: {endpoint} · 모델: {args.model} · 원문 {len(value['evidence'])}개 / {value['budget']['source_characters']}자", file=sys.stderr)
                try:
                    value = explain(value, base_url=args.base_url, model=args.model,
                                    api_key=os.environ.get("KNITCODE_AI_API_KEY", ""), timeout=args.timeout)
                except AIError as error:
                    value = {"status": "failed", "error": str(error), "endpoint": endpoint, "model": args.model,
                             "snapshot_id": value["snapshot_id"], "input_hash": value["input_hash"],
                             "prompt_version": value["prompt_version"], "context": value}
                    status = 3
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(to_json(value))
            print(f"저장: {output}", file=sys.stderr)
        else:
            sys.stdout.write(to_json(value))
        return status
    except KeyboardInterrupt:
        print("취소되었습니다.", file=sys.stderr)
        return 130
    except (ValueError, OSError) as error:
        print(f"knitcode assist: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
