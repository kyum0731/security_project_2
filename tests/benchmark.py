"""Repeatable local measurements. Run from prototype_2 with python -m tests.benchmark."""

import argparse
import json
import os
from pathlib import Path
import platform
import statistics
import time

from knitcode_analyzer_v2 import analyze_project
from knitcode_analyzer_v2.exporter import write_report, verify_manifest


def measure(project, *, source_root=None, excludes=(), report_dir, runs=3):
    if runs < 3:
        raise ValueError("측정은 최소 3회 실행합니다.")
    durations = []
    for _ in range(runs):
        started = time.perf_counter()
        result = analyze_project(project, source_root=source_root, excludes=excludes, excluded_paths=(report_dir,))
        durations.append(round(time.perf_counter() - started, 4))
    write_report(result, report_dir)
    assert verify_manifest(report_dir)
    return {"project_root": str(Path(project).resolve()), "source_root": source_root or ".",
            "python": platform.python_version(), "platform": platform.platform(),
            "processor": platform.processor(), "logical_cpus": os.cpu_count(),
            "ram": "not measured", "runs_seconds": durations, "median_seconds": statistics.median(durations),
            "timing_scope": "analysis API including insights and invariants; excludes report rendering and disk output; OS cache not cleared",
            "physical_lines": sum(len((Path(project) / f["path"]).read_bytes().splitlines()) for f in result["files"]),
            "stats": result["stats"], "analysis_status": result["metadata"]["analysis_status"],
            "snapshot_id": result["metadata"]["snapshot_id"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("--source-root")
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--report-dir", required=True)
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    print(json.dumps(measure(args.project, source_root=args.source_root, excludes=args.exclude,
                             report_dir=args.report_dir, runs=args.runs), ensure_ascii=False, indent=2))
