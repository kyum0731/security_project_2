"""Conservative, project-local resolution. Never imports or executes target code."""

from __future__ import annotations

import ast
import builtins
from collections import defaultdict

from .models import Binding, Collection, Resolution, Scope, SourceFile


def unresolved(reason: str) -> Resolution:
    return Resolution("unresolved", reason=reason)


class Resolver:
    def __init__(self, files: list[SourceFile], blocked_modules=()):
        self.modules: dict[str, list[SourceFile]] = defaultdict(list)
        self.blocked_modules = set(blocked_modules)
        for file in files:
            self.modules[file.module].append(file)

    def module(self, name: str) -> Resolution:
        matches = self.modules.get(name, [])
        if len(matches) > 1:
            return unresolved("ambiguous_module")
        if matches:
            file = matches[0]
            if file.tree is None:
                return unresolved("parse_error")
            return Resolution("resolved", target=file.node_id, module=file, rule="indexed_module")
        # An absent member of a local package is not evidence of an external import.
        top = name.split(".")[0]
        if any(name == key or name.startswith(key + ".") for key in self.blocked_modules):
            return unresolved("module_not_indexed")
        if any(key == top or key.startswith(top + ".") for key in self.modules):
            return unresolved("module_not_indexed")
        return Resolution("external", external_name=name)

    def import_target(self, record: dict, *, binding: bool = False) -> Resolution:
        name = record["name"]
        if name == "*":
            return unresolved("unsupported_syntax")
        if record["kind"] == "import":
            full = self.module(name)
            if binding and not record["alias"] and "." in name:
                # `import pkg.mod` binds pkg, while the import edge points to pkg.mod.
                if full.status == "external":
                    return Resolution("external", external_name=name.split(".")[0])
                if full.status != "resolved":
                    return full
                return self.module(name.split(".")[0])
            return full

        module_name = record["module"] or ""
        if record["level"]:
            file = record["scope"].file
            package = file.module.split(".") if file.is_package else file.module.split(".")[:-1]
            if not package or record["level"] > len(package):
                return unresolved("invalid_relative_import")
            base = package[:len(package) - record["level"] + 1]
            module_name = ".".join([*base, *([module_name] if module_name else [])])
        module = self.module(module_name)
        if module.status == "external":
            return Resolution("external", external_name=".".join(filter(None, [module_name, name])))
        if module.status != "resolved":
            return module
        return self.member(module.module, name, allow_submodule=True)

    def select(self, bindings: list[Binding], scope: Scope, call: ast.Call | None = None) -> Resolution:
        if any(binding.kind == "parameter" for binding in bindings):
            return unresolved("parameter_call" if len(bindings) == 1 else "shadowed_name")
        if any(binding.kind == "assignment" for binding in bindings):
            return unresolved("shadowed_name")
        if len(bindings) != 1 or bindings[0].conditional:
            return unresolved("ambiguous_definition")
        item = bindings[0]
        if item.decorated:
            return unresolved("unsupported_syntax")
        # The binding is only available after the definition/import statement.
        # A call in f's own default argument must not resolve to the new f.
        if call is not None and (call.lineno, call.col_offset) < (item.node.end_lineno, item.node.end_col_offset):
            return unresolved("unsupported_syntax")
        if scope.wildcard:
            return unresolved("unsupported_syntax")
        if item.kind == "definition":
            return Resolution("resolved", target=item.target, rule="lexical_definition")
        if item.kind == "import":
            result = self.import_target(item.import_record, binding=True)
            if result.status == "resolved":
                result.rule = "explicit_import_alias" if item.import_record["alias"] else "explicit_import"
            return result
        return unresolved("unsupported_syntax")

    def member(self, file: SourceFile, name: str, *, allow_submodule: bool) -> Resolution:
        scope = file.scope
        if scope.wildcard:
            return unresolved("unsupported_syntax")
        bindings = scope.bindings.get(name, [])
        if bindings:
            # No chains through re-exports, even when their spelling seems unambiguous.
            if any(binding.kind == "import" for binding in bindings):
                return unresolved("unsupported_syntax")
            return self.select(bindings, scope)
        submodule = f"{file.module}.{name}"
        if file.is_package and allow_submodule:
            return self.module(submodule)
        return unresolved("name_not_found")

    def name(self, scope: Scope, name: str, call: ast.Call) -> Resolution:
        if name in scope.globals or name in scope.nonlocals:
            return unresolved("unsupported_syntax")
        if scope.wildcard:
            return unresolved("unsupported_syntax")
        if name in scope.bindings:
            return self.select(scope.bindings[name], scope, call)
        parent = scope.parent
        deferred = scope.kind in {"function", "lambda"}
        while parent:
            if parent.kind in {"function", "lambda", "comprehension"}:
                if name in parent.bindings or name in parent.nonlocals or name in parent.globals:
                    return unresolved("unsupported_syntax")
                deferred = deferred or parent.kind in {"function", "lambda"}
            elif parent.kind == "file":
                if parent.wildcard:
                    return unresolved("unsupported_syntax")
                if name in parent.bindings:
                    return self.select(parent.bindings[name], parent, None if deferred else call)
            # Class attributes are not lexical variables for a method body.
            parent = parent.parent
        if callable(getattr(builtins, name, None)):
            return Resolution("builtin", builtin_name=name, rule="builtin_name")
        return unresolved("name_not_found")

    def call(self, scope: Scope, call: ast.Call) -> Resolution:
        expression = call.func
        if isinstance(expression, ast.Name):
            result = self.name(scope, expression.id, call)
        elif isinstance(expression, ast.Attribute):
            attributes = []
            root = expression
            while isinstance(root, ast.Attribute):
                attributes.append(root.attr)
                root = root.value
            if not isinstance(root, ast.Name):
                return unresolved("dynamic_dispatch")
            result = self.name(scope, root.id, call)
            if result.status == "unresolved":
                if result.reason in {"parameter_call", "name_not_found"}:
                    return unresolved("dynamic_dispatch")
                return result
            for name in reversed(attributes):
                if result.status == "external":
                    result.external_name += "." + name
                elif result.module is not None:
                    # Only descend into a submodule if an explicit dotted import
                    # in this lexical environment proves that it was requested.
                    dotted = f"{result.module.module}.{name}"
                    result = self.member(result.module, name, allow_submodule=self.has_dotted_import(scope, dotted))
                else:
                    return unresolved("dynamic_dispatch")
                if result.status == "unresolved":
                    return result
        else:
            return unresolved("dynamic_dispatch")
        if result.module is not None:
            return unresolved("unsupported_syntax")  # A module itself is not callable.
        if result.status == "resolved" and isinstance(expression, ast.Attribute):
            result.rule = "explicit_module_member"
        return result

    @staticmethod
    def has_dotted_import(scope: Scope, module: str) -> bool:
        current = scope
        while current:
            if current is scope or current.kind == "file":
                for bindings in current.bindings.values():
                    for item in bindings:
                        record = item.import_record
                        if record and record["kind"] == "import" and (record["name"] == module or record["name"].startswith(module + ".")):
                            return True
            current = current.parent
        return False

    def resolve(self, collection: Collection):
        for record in collection.imports:
            node, scope = record["node"], record["scope"]
            collection.edges.append({
                "type": "imports", "source": scope.node_id,
                **self.import_target(record).fields(),
                "name": record["name"], "alias": record["alias"],
                "alias_index": record["alias_index"],
                "module": record["module"], "level": record["level"], "import_kind": record["kind"],
                "expression": scope.file.text(node), "evidence": evidence(scope.file, node),
                "analyzer": "ast-import-resolution",
            })
        for file, scope, node, context in collection.calls:
            collection.edges.append({
                "type": "calls", "source": scope.node_id, **self.call(scope, node).fields(),
                "expression": file.text(node), "evidence": evidence(file, node),
                "context": context,
                "analyzer": "ast-import-resolution",
            })


def evidence(file: SourceFile, node: ast.AST) -> dict:
    return {"file": file.relative, "line": node.lineno, "col": node.col_offset,
            "end_line": node.end_lineno, "end_col": node.end_col_offset}
