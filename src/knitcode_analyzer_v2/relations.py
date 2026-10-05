"""Lexical symbol relations; no value, alias, object-type or control-flow inference."""

import ast

from .models import location
from .resolver import evidence


def collect_relations(collection, resolver):
    variables = {}
    nodes = {n["id"]: n for n in collection.nodes}
    scopes = {s.node_id: s for s in collection.scopes}
    files = {s.node_id: s.file for s in collection.scopes if s.kind == "file"}

    def add(kind, scope, syntax, target, *, source=None, context=None, reason=None):
        edge = {"type": kind, "source": source or scope.node_id, "target": target,
                "resolution_status": "resolved" if target else "unresolved",
                "resolution_rule": "lexical_symbol_reference", "reason": reason,
                "expression": scope.file.text(syntax), "evidence": evidence(scope.file, syntax)}
        if context:
            edge["context"] = context
        collection.edges.append(edge)

    for scope in collection.scopes:
        for name, bindings in scope.bindings.items():
            # Mutating obj.attr is not a new lexical variable named obj. A mixture
            # with imports/definitions is deliberately not assigned one identity.
            if any(b.kind not in {"assignment", "parameter"} for b in bindings):
                continue
            declarations = [b for b in bindings if not isinstance(b.node, ast.Attribute)]
            if not declarations:
                continue
            first = min(declarations, key=lambda b: (b.node.lineno, b.node.col_offset))
            qualname = ".".join(filter(None, [scope.qualified_name, name]))
            node_id = f"{scope.file.relative}::variable:{qualname}@{first.node.lineno}:{first.node.col_offset}"
            item = {"id": node_id, "type": "variable", "name": name,
                    "qualified_name": qualname, "file": scope.file.relative,
                    "parent": scope.node_id, "range": location(first.node), "docstring": None,
                    "variable_kind": "parameter" if any(b.kind == "parameter" for b in bindings)
                    else {"file": "module", "class": "class_attribute", "function": "local"}[scope.kind]}
            collection.nodes.append(item)
            nodes[node_id] = item
            variables[id(scope), name] = node_id
            collection.edges.append({"type": "contains", "source": scope.node_id,
                                     "target": node_id, "evidence": evidence(scope.file, first.node)})

    def owner(scope, name):
        if name in scope.globals:
            while scope.parent:
                scope = scope.parent
            return scope
        if name in scope.nonlocals:
            parent = scope.parent
            while parent:
                if parent.kind in {"function", "lambda"} and name in parent.bindings:
                    return parent
                parent = parent.parent
            return None
        current = scope
        while current:
            if current.wildcard:
                return None
            if current is scope or current.kind != "class":
                if name in current.bindings:
                    return current
                if name in current.globals or name in current.nonlocals:
                    return owner(current, name)
            current = current.parent
        return None

    def binding(scope, name, trail=()):
        key = (id(scope), name)
        if key in trail or scope.wildcard:
            return None
        if key in variables:
            return variables[key]
        values = scope.bindings.get(name, [])
        if len(values) != 1 or values[0].conditional:
            return None
        value = values[0]
        if value.kind == "definition":
            return value.target
        if value.kind != "import":
            return None
        record = value.import_record
        resolved = resolver.import_target(record, binding=True)
        if resolved.status == "resolved":
            return resolved.target
        # Explicit imports of lexical variables are supported only at their
        # defining module. Re-exports remain outside this analysis contract.
        if record["kind"] != "from" or record["name"] == "*":
            return None
        module = record["module"] or ""
        if record["level"]:
            file = scope.file
            package = file.module.split(".") if file.is_package else file.module.split(".")[:-1]
            if not package or record["level"] > len(package):
                return None
            module = ".".join(package[:len(package) - record["level"] + 1] + ([module] if module else []))
        match = resolver.module(module)
        if match.status != "resolved":
            return None
        if match.module.scope.wildcard:
            return None
        return variables.get((id(match.module.scope), record["name"]))

    def expression(scope, node):
        if isinstance(node, ast.Name):
            found = owner(scope, node.id)
            if found and found.kind == "class" and found is scope:
                # Class bodies use execution-ordered namespace lookup; a later
                # class assignment must not capture an earlier global read.
                declarations = found.bindings.get(node.id, [])
                if isinstance(node.ctx, ast.Load) and declarations and all(
                        b.node.end_lineno >= node.lineno
                        for b in declarations):
                    return None
            return binding(found, node.id) if found else None
        if isinstance(node, ast.Attribute):
            root = expression(scope, node.value)
            if root in files:
                target_scope = files[root].scope
            elif root in scopes and nodes[root]["type"] == "class":
                target_scope = scopes[root]
            else:
                return None
            # No inherited lookup, descriptors, object or assignment aliases.
            return binding(target_scope, node.attr)
        return None

    for record, edge in zip(collection.imports, [e for e in collection.edges if e["type"] == "imports"]):
        if record["kind"] == "from" and edge["resolution_status"] == "unresolved":
            name = record["alias"] or record["name"]
            target = binding(record["scope"], name)
            if target and nodes[target]["type"] == "variable":
                edge.update(target=target, resolution_status="resolved", reason=None,
                            resolution_rule="explicit_import_variable")

    for scope, syntax, kind, context in collection.uses:
        if scope.kind in {"lambda", "comprehension"}:
            continue
        target = expression(scope, syntax)
        if target is None:
            continue
        if nodes[target]["type"] == "variable":
            add(kind, scope, syntax, target, context=context)
        elif kind == "reads":
            add("references", scope, syntax, target, context=context)

    for scope, source, base in collection.bases:
        # Resolve base expressions with the conservative existing resolver:
        # decorators, assignments, generic bases and factories stay unresolved.
        call = ast.Call(func=base, args=[], keywords=[])
        ast.copy_location(call, base)
        resolved = resolver.call(scope, call)
        target = resolved.target if resolved.status == "resolved" else None
        if target and nodes[target]["type"] != "class":
            target = None
        add("inherits", scope, base, target, source=source,
            reason=None if target else (resolved.reason or "unsupported_base"))

    def loaded_names(node):
        if isinstance(node, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            return
        if isinstance(node, (ast.Name, ast.Attribute)) and isinstance(node.ctx, ast.Load):
            yield node
        for child in ast.iter_child_nodes(node):
            yield from loaded_names(child)

    for scope, statement, targets, value in collection.assignments:
        if scope.kind in {"lambda", "comprehension"}:
            continue
        sources = {expression(scope, t) for t in targets if isinstance(t, ast.Name)}
        dependencies = {expression(scope, n) for n in loaded_names(value)}
        for source in sources:
            if source is None or nodes[source]["type"] != "variable":
                continue
            for target in sorted(t for t in dependencies if t and nodes[t]["type"] == "variable"):
                add("depends_on", scope, statement, target, source=source)
