"""Shared internal models. Public results consist only of JSON-compatible values."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VERSION = "0.2.1"
SCHEMA_VERSION = "2.0"


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


class AnalysisResult(dict):
    """JSON-compatible public result; to_dict returns an independent copy."""

    def to_dict(self) -> dict:
        return copy.deepcopy(dict(self))


def location(node: ast.AST) -> dict[str, int]:
    return {
        "start_line": node.lineno,
        "start_col": node.col_offset,
        "end_line": node.end_lineno,
        "end_col": node.end_col_offset,
    }


@dataclass
class SourceFile:
    path: Path
    relative: str
    module: str
    is_package: bool
    source: str = ""
    tree: ast.Module | None = None
    content_hash: str | None = None
    scope: Scope | None = None
    encoding: str | None = None
    parse_status: str = "read_error"

    @property
    def node_id(self) -> str:
        return f"{self.relative}::<module>@1:0"

    def text(self, node: ast.AST | None) -> str | None:
        if node is None:
            return None
        return ast.get_source_segment(self.source, node) or ast.unparse(node)


@dataclass
class Binding:
    kind: str
    node: ast.AST
    target: str | None = None
    import_record: dict[str, Any] | None = None
    conditional: bool = False
    decorated: bool = False


@dataclass
class Scope:
    kind: str
    node_id: str
    qualified_name: str
    file: SourceFile
    parent: Scope | None = None
    bindings: dict[str, list[Binding]] = field(default_factory=dict)
    globals: set[str] = field(default_factory=set)
    nonlocals: set[str] = field(default_factory=set)
    wildcard: bool = False


@dataclass
class Collection:
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    imports: list[dict[str, Any]] = field(default_factory=list)
    calls: list[tuple[SourceFile, Scope, ast.Call, str]] = field(default_factory=list)


@dataclass
class Resolution:
    status: str
    target: str | None = None
    reason: str | None = None
    external_name: str | None = None
    module: SourceFile | None = None
    builtin_name: str | None = None
    rule: str = "conservative_name_resolution"

    def fields(self) -> dict[str, Any]:
        result = {"resolution_status": self.status, "target": self.target, "resolution_rule": self.rule}
        if self.reason:
            result["reason"] = self.reason
        if self.external_name:
            result["external_name"] = self.external_name
            result["origin_verified"] = False
        if self.builtin_name:
            result["builtin_name"] = self.builtin_name
        return result
