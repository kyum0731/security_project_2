import argparse
import hashlib
from pathlib import Path
import sys

from .analyzer import analyze_project
from .exporter import to_json, validate_output_directory, write_report
from .models import VERSION


def main(argv=None):
    parser = argparse.ArgumentParser(description="로컬 Python 프로젝트를 실행하지 않고 분석하여 한국어 구조 보고서를 만듭니다.")
    parser.add_argument("project", help="분석할 로컬 디렉터리 (필수)")
    parser.add_argument("--source-root", help="프로젝트 내부 분석·import 기준 상대 디렉터리 (기본: .)")
    parser.add_argument("--exclude", action="append", default=[], metavar="PATTERN", help="상대 POSIX 제외 패턴. 반복 가능: --exclude 'tests/'")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--report-dir", help="보고서 전용 출력 디렉터리")
    output.add_argument("--json-stdout", action="store_true", help="파일 없이 UTF-8 JSON 하나만 stdout으로 출력")
    parser.add_argument("--strict", action="store_true", help="부분 분석·Python 파일 없음일 때 결과와 함께 종료 코드 1")
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        project = Path(args.project).expanduser().resolve()
        directory = None
        if not args.json_stdout:
            root_hash = hashlib.sha256(str(project).encode("utf-8")).hexdigest()[:10]
            directory = Path(args.report_dir) if args.report_dir else Path.cwd() / "knitcode-reports" / f"{project.name}-{root_hash}"
            directory = validate_output_directory(directory, project, project / (args.source_root or "."))
        result = analyze_project(project, source_root=args.source_root, excludes=args.exclude,
                                 excluded_paths=[directory] if directory else ())
        if args.json_stdout:
            sys.stdout.write(to_json(result))
        else:
            artifacts = write_report(result, directory)
            print(f"보고서: {artifacts['report.html']}", file=sys.stderr)
        stats = result["stats"]
        print(f"상태: {result['metadata']['analysis_status']} · Python 파일 {stats['file_count']} · 정의 {stats['definition_count']} · 호출 {stats['call_count']} · 파싱 실패 {stats['parse_failed_file_count']}", file=sys.stderr)
        return 1 if args.strict and result["metadata"]["analysis_status"] != "complete" else 0
    except KeyboardInterrupt:
        print("분석이 취소되었습니다.", file=sys.stderr)
        return 130
    except (ValueError, OSError) as error:
        print(f"knitcode-analyzer-v2: {error}", file=sys.stderr)
        return 2
