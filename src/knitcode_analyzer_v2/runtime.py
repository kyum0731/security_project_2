"""Explicit execution command: analysis stays read-only; the worker executes code."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import uuid

from .analyzer import analyze_project
from .exporter import to_json, validate_output_directory, write_report
from .runtime_trace import summarize


def inside(root, value, *, directory=False):
    candidate = Path(value).expanduser()
    candidate = candidate if candidate.is_absolute() else root / candidate
    path = candidate.resolve()
    if not path.is_relative_to(root) or (not path.is_dir() if directory else not path.is_file()):
        raise ValueError("프로젝트 내부의 존재하는 경로가 필요합니다: " + str(value))
    for part in (candidate.absolute(), *candidate.absolute().parents):
        if part == root:
            break
        if part.is_symlink() or part.is_junction():
            raise ValueError("실행 경로에 링크를 사용할 수 없습니다.")
    return path


def drain(pipe, destination, limit, stats, control):
    """Continue draining past the cap so a chatty target cannot block on its pipe."""
    total = 0
    try:
        with destination.open("xb") as stream:
            with control["lock"]:
                control["stream"] = stream
            while chunk := pipe.read(8192):
                with control["lock"]:
                    if control["stopped"]:
                        break
                    remaining = max(0, limit - total)
                    if remaining:
                        stream.write(chunk[:remaining])
                    total += len(chunk)
                    stats.update(bytes_seen=total, bytes_saved=min(limit, total), truncated=total > limit)
    except (OSError, ValueError):
        with control["lock"]:
            if not control["stopped"]:
                stats["read_error"] = True
    finally:
        with control["lock"]:
            if not control["stopped"]:
                stats.update(bytes_seen=total, bytes_saved=min(limit, total), truncated=total > limit)
        pipe.close()


def read_events(path, max_events):
    events, invalid = [], False
    if not path.exists():
        return events, True
    with path.open("rb") as stream:
        for index in range(max_events + 2):
            raw = stream.readline(262145)
            if not raw:
                break
            if index > max_events or len(raw) > 262144 or not raw.endswith(b"\n"):
                invalid = True
                break
            try:
                event = json.loads(raw)
                if not isinstance(event, dict) or event.get("seq") != index + 1 or event.get("event") not in {"start", "return", "raise", "unwind", "limitation"}:
                    raise ValueError("Invalid runtime event")
                events.append(event)
            except (ValueError, UnicodeError):
                invalid = True
                break
    return events, invalid


def verify_run(directory):
    directory = Path(directory)
    try:
        manifest = json.loads((directory / "run-manifest.json").read_text(encoding="utf-8"))
        names = {"analysis.json", "report.html", "report.md", "manifest.json", "run.json", "summary.json", "events.jsonl", "stdout.log", "stderr.log"}
        return (manifest["producer"] == "knitcode_runtime" and set(manifest["artifacts"]) == names
                and all(hashlib.sha256((directory / name).read_bytes()).hexdigest() == value for name, value in manifest["artifacts"].items())
                and json.loads((directory / "run.json").read_text(encoding="utf-8"))["run_id"] == manifest["run_id"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


def run_project(project, *, script=None, module=None, args=(), cwd=".", python=None, source_root=None,
                excludes=(), report_dir=None, timeout=60, max_events=50000, max_log_bytes=1048576):
    if bool(script) == bool(module):
        raise ValueError("--script 또는 --module 중 하나를 지정하세요.")
    if not 0.1 <= timeout <= 3600 or not 1 <= max_events <= 500000 or not 0 <= max_log_bytes <= 10485760:
        raise ValueError("timeout 0.1~3600초, max-events 1~500000, max-log-bytes 0~10485760 범위가 필요합니다.")
    root = Path(project).expanduser().resolve()
    working = inside(root, cwd, directory=True)
    entry = inside(root, script) if script else None
    if entry and entry.suffix != ".py":
        raise ValueError("스크립트는 .py 파일이어야 합니다.")
    if module and not re.fullmatch(r"[A-Za-z_\w]+(?:\.[A-Za-z_\w]+)*", module):
        raise ValueError("유효한 Python 모듈 이름이 필요합니다.")
    root_hash = hashlib.sha256(str(root).encode()).hexdigest()[:10]
    base = Path(report_dir) if report_dir else Path.cwd() / "knitcode-reports" / f"{root.name}-{root_hash}"
    base = validate_output_directory(base, root, root / (source_root or "."))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:12]
    directory = base / "runs" / run_id
    if (base / "runs").is_symlink() or (base / "runs").is_junction():
        raise ValueError("runs 디렉터리로 링크를 사용할 수 없습니다.")
    analysis = analyze_project(root, source_root=source_root, excludes=excludes, excluded_paths=(base,))
    if entry and not any(f["path"] == entry.relative_to(root).as_posix() and f["parse_status"] == "ok" for f in analysis["files"]):
        raise ValueError("실행 스크립트는 정적 분석 범위에 포함되고 파싱에 성공해야 합니다.")
    directory.mkdir(parents=True, exist_ok=False)
    executable = str(Path(python).expanduser().resolve()) if python and ("/" in python or "\\" in python) else python or sys.executable
    config = {"analysis": analysis, "directory": str(directory), "cwd": str(working), "script": str(entry) if entry else None,
              "module": module, "args": list(args), "max_events": max_events}
    config_path = directory / "worker-input.json"
    config_path.write_text(to_json(config), encoding="utf-8")
    started = time.perf_counter()
    run = {"runtime_schema_version": "1.0", "run_id": run_id, "snapshot_id": analysis["metadata"]["snapshot_id"],
           "started_at": datetime.now(timezone.utc).isoformat(), "project_root": root.as_posix(), "cwd": working.as_posix(),
           "script": entry.relative_to(root).as_posix() if entry else None, "module": module, "args": list(args),
           "requested_python": executable, "timeout_seconds": timeout, "max_events": max_events,
           "max_log_bytes_per_stream": max_log_bytes, "execution_status": "finished", "trace_status": "partial",
           "target_exit_code": None, "logs": {"stdout": {}, "stderr": {}},
           "scope": "single initial thread; synchronous Python code; no values; child processes not instrumented",
           "limitations": []}
    process, threads, controls = None, [], []
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        process = subprocess.Popen([executable, "-u", "-B", str(Path(__file__).with_name("_runtime_worker.py")), str(config_path)],
                                   cwd=working, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   shell=False, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        for name, pipe in (("stdout", process.stdout), ("stderr", process.stderr)):
            control = {"lock": threading.Lock(), "stopped": False, "stream": None}
            controls.append(control)
            thread = threading.Thread(target=drain, args=(pipe, directory / (name + ".log"), max_log_bytes, run["logs"][name], control), daemon=True)
            thread.start()
            threads.append(thread)
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            run["execution_status"] = "timeout"
            process.kill()
            process.wait(timeout=5)
        except KeyboardInterrupt:
            run["execution_status"] = "cancelled"
            process.kill()
            process.wait(timeout=5)
        run["target_exit_code"] = process.returncode
    except OSError as error:
        run["execution_status"] = "launch_failed"
        run["launch_error"] = str(error)
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        for thread in threads:
            thread.join(timeout=2)
        if any(thread.is_alive() for thread in threads):
            run["limitations"].append("log_pipe_still_open_possible_child_process")
        # Freeze output before hashing. Descendants may retain inherited pipe handles;
        # late output must never change a published run's log files or metadata.
        for control in controls:
            with control["lock"]:
                control["stopped"] = True
                if control["stream"] is not None and not control["stream"].closed:
                    control["stream"].flush()
                    control["stream"].close()
        run["elapsed_seconds"] = round(time.perf_counter() - started, 6)
        config_path.unlink(missing_ok=True)
    worker_path = directory / "worker-status.json"
    try:
        worker = json.loads(worker_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        worker = {"worker_completed": False, "limitations": ["worker_status_missing"]}
    worker_path.unlink(missing_ok=True)
    run["worker"] = worker
    for name in ("events.jsonl", "stdout.log", "stderr.log"):
        if not (directory / name).exists():
            (directory / name).touch()
    events, invalid = read_events(directory / "events.jsonl", max_events)
    summary = summarize(analysis, events)
    changed = []
    for file in analysis["files"]:
        if file["sha256"]:
            try:
                actual = hashlib.sha256((root / file["path"]).read_bytes()).hexdigest()
            except OSError:
                actual = None
            if actual != file["sha256"]:
                changed.append(file["path"])
    run["changed_files"] = changed
    reasons = set(run["limitations"] + summary["limitations"] + worker.get("limitations", []))
    if changed:
        reasons.add("source_changed")
    if invalid:
        reasons.add("incomplete_event_stream")
    if analysis["metadata"]["analysis_status"] != "complete":
        reasons.add("static_analysis_" + analysis["metadata"]["analysis_status"])
    if run["execution_status"] != "finished":
        reasons.add(run["execution_status"])
    run["limitations"] = sorted(reasons)
    run["trace_status"] = "complete_within_scope" if not reasons and worker.get("worker_completed") else "partial"
    if run["execution_status"] == "finished" and run["target_exit_code"] != 0:
        run["execution_status"] = "failed"
    summary["limitations"] = run["limitations"]
    summary["run_id"] = run_id
    runtime = {"run": run, "summary": summary, "events": events}
    (directory / "run.json").write_text(to_json(run), encoding="utf-8")
    (directory / "summary.json").write_text(to_json(summary), encoding="utf-8")
    write_report(analysis, directory, runtime=runtime)
    names = ("analysis.json", "report.html", "report.md", "manifest.json", "run.json", "summary.json", "events.jsonl", "stdout.log", "stderr.log")
    manifest = {"producer": "knitcode_runtime", "run_id": run_id, "snapshot_id": analysis["metadata"]["snapshot_id"],
                "artifacts": {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in names}}
    (directory / "run-manifest.json").write_text(to_json(manifest), encoding="utf-8")
    return directory, runtime


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    target_args = []
    if "--" in argv:
        index = argv.index("--")
        argv, target_args = argv[:index], argv[index + 1:]
    parser = argparse.ArgumentParser(description="대상 Python 코드를 실제 실행해 동기 호출을 관측합니다. 파일 변경·네트워크 요청이 발생할 수 있으며 샌드박스가 아닙니다.")
    parser.add_argument("project")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--script", help="프로젝트 내부 .py 스크립트")
    target.add_argument("--module", help="실행할 Python 모듈 (예: unittest)")
    parser.add_argument("--python", help="대상 의존성이 설치된 CPython 3.13+ 실행 파일")
    parser.add_argument("--cwd", default=".", help="프로젝트 내부 작업 디렉터리 (기본 프로젝트 루트)")
    parser.add_argument("--source-root")
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--report-dir")
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--max-events", type=int, default=50000)
    parser.add_argument("--max-log-bytes", type=int, default=1048576)
    options = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        print("대상 코드를 실제 실행합니다. 입력은 비대화형이며 stdout/stderr는 결과 폴더에 저장합니다.", file=sys.stderr)
        directory, result = run_project(options.project, script=options.script, module=options.module, args=target_args,
                                        cwd=options.cwd, python=options.python, source_root=options.source_root,
                                        excludes=options.exclude, report_dir=options.report_dir, timeout=options.timeout,
                                        max_events=options.max_events, max_log_bytes=options.max_log_bytes)
        run = result["run"]
        print(f"동적 보고서: {directory / 'report.html'}\n실행: {run['execution_status']} · 추적: {run['trace_status']} · 대상 종료 코드: {run['target_exit_code']}", file=sys.stderr)
        if run["execution_status"] == "cancelled":
            return 130
        if run["execution_status"] == "timeout":
            return 124
        return 0 if run["execution_status"] == "finished" and run["trace_status"] == "complete_within_scope" else 1
    except KeyboardInterrupt:
        return 130
    except (ValueError, OSError) as error:
        print(f"knitcode runtime: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
