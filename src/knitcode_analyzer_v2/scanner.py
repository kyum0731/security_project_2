"""Deterministic scanning with explicit boundaries and inspectable exclusions."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .models import SourceFile

EXCLUDED = frozenset({".git", ".venv", "venv", "env", "__pycache__", "site-packages",
                      "node_modules", "build", "dist", ".tox", ".mypy_cache",
                      ".pytest_cache", ".ruff_cache"})


def compile_pattern(pattern: str) -> re.Pattern:
    if not pattern or pattern.startswith(("!", "/")) or "\\" in pattern or ".." in pattern.split("/"):
        raise ValueError(f"프로젝트 상대 POSIX 제외 패턴이 필요합니다: {pattern!r}")
    directory = pattern.endswith("/")
    pattern = pattern.rstrip("/")
    result, i = "", 0
    while i < len(pattern):
        if pattern[i:i + 3] == "**/":
            result += "(?:[^/]+/)*"
            i += 3
        elif pattern[i:i + 2] == "**":
            result += ".*"
            i += 2
        else:
            result += "[^/]*" if pattern[i] == "*" else "[^/]" if pattern[i] == "?" else re.escape(pattern[i])
            i += 1
    return re.compile("^" + result + ("(?:/.*)?" if directory else "") + "$")


def module_name(relative: Path) -> tuple[str, bool]:
    parts = list(relative.with_suffix("").parts)
    package = parts[-1] == "__init__"
    if package:
        parts.pop()
    return ".".join(parts), package


@dataclass
class ScanResult:
    project: Path
    source: Path
    files: list[SourceFile] = field(default_factory=list)
    diagnostics: list[dict] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    blocked_modules: set[str] = field(default_factory=set)


def scan_project(root, source_root=None, excludes=(), excluded_paths=()) -> ScanResult:
    project = Path(root).expanduser().resolve()
    if not project.is_dir():
        raise ValueError(f"프로젝트 디렉터리가 없습니다: {project}")
    if source_root is not None and Path(source_root).is_absolute():
        raise ValueError("--source-root는 프로젝트 내부 상대 경로여야 합니다.")
    source = (project / (source_root or ".")).resolve()
    if not source.is_dir() or not source.is_relative_to(project):
        raise ValueError("소스 루트는 프로젝트 내부의 존재하는 디렉터리여야 합니다.")
    patterns = [compile_pattern(p) for p in excludes]
    output_paths = {Path(p).resolve() for p in excluded_paths}
    result = ScanResult(project, source)
    pending = [source]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                entries = sorted(entries, key=lambda e: e.name)
        except OSError as error:
            if directory == source:
                raise ValueError(f"입력 루트를 읽을 수 없습니다: {source}") from error
            result.diagnostics.append({"file": directory.relative_to(project).as_posix(),
                                       "code": "scan_error", "severity": "error", "message": str(error)})
            continue
        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(project).as_posix()
            try:
                linked = path.is_symlink() or path.is_junction()
                is_dir = entry.is_dir(follow_symlinks=False) if not linked else path.is_dir()
                reason = ("link_skipped" if linked else
                          "output_directory" if path.resolve() in output_paths else
                          "default_exclusion" if is_dir and entry.name in EXCLUDED else
                          "user_exclusion" if any(p.fullmatch(relative) or (is_dir and p.fullmatch(relative + "/"))
                                                  for p in patterns) else None)
                if reason:
                    result.skipped.append({"path": relative, "kind": "directory" if is_dir else "file", "reason": reason})
                    module, _ = module_name(path.relative_to(source)) if not is_dir else (".".join(path.relative_to(source).parts), False)
                    if module:
                        result.blocked_modules.add(module)
                elif is_dir:
                    pending.append(path)
                elif path.suffix == ".py" and entry.is_file(follow_symlinks=False):
                    module, package = module_name(path.relative_to(source))
                    result.files.append(SourceFile(path, relative, module, package))
            except OSError as error:
                result.diagnostics.append({"file": relative, "code": "scan_error", "severity": "error", "message": str(error)})
    result.files.sort(key=lambda f: f.relative)
    result.skipped.sort(key=lambda item: item["path"])
    return result

