"""Collect definitions, lexical bindings and call syntax before resolving names."""

from __future__ import annotations

import ast

from .models import Binding, Collection, Scope, SourceFile, location


class SymbolCollector(ast.NodeVisitor):
    def __init__(self, file: SourceFile, result: Collection):
        self.file = file
        self.result = result
        self.scope = Scope("file", file.node_id, "", file)
        file.scope = self.scope
        self.conditional = 0
        self.nonlocal_writes = []
        self.context = "module_body"

    def bind(self, name: str, binding: Binding):
        target = self.scope
        if name in target.globals:
            while target.parent:
                target = target.parent
        elif name in target.nonlocals:
            # Apply after collecting all definitions, including later outer bindings.
            self.nonlocal_writes.append((target, name, binding))
            return
        target.bindings.setdefault(name, []).append(binding)

    def collect(self):
        lines = self.file.source.split("\n")
        self.result.nodes.append({
            "id": self.file.node_id, "type": "file", "name": self.file.relative,
            "qualified_name": "", "file": self.file.relative, "parent": None,
            "range": {"start_line": 1, "start_col": 0, "end_line": max(1, len(lines)),
                      "end_col": len(lines[-1].rstrip("\r").encode("utf-8")) if lines else 0}
                     if self.file.parse_status not in {"read_error", "decode_error"} else None,
            "docstring": ast.get_docstring(self.file.tree, clean=False) if self.file.tree else None,
        })
        if self.file.tree:
            self.visit(self.file.tree)
        for scope, name, binding in self.nonlocal_writes:
            parent = scope.parent
            while parent:
                if parent.kind in {"function", "lambda"} and name in parent.bindings:
                    parent.bindings[name].append(binding)
                    break
                parent = parent.parent

    def definition(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        parent = self.scope
        qualname = ".".join(filter(None, [parent.qualified_name, node.name]))
        node_id = f"{self.file.relative}::{qualname}@{node.lineno}:{node.col_offset}"
        is_class = isinstance(node, ast.ClassDef)
        kind = "class" if is_class else ("method" if parent.kind == "class" else "function")
        self.bind(node.name, Binding("definition", node, target=node_id,
                                    conditional=bool(self.conditional), decorated=bool(node.decorator_list)))
        item = {"id": node_id, "type": kind, "name": node.name,
                "qualified_name": qualname, "file": self.file.relative,
                "range": location(node), "parent": parent.node_id,
                "docstring": ast.get_docstring(node, clean=False)}
        if not is_class:
            item.update(is_async=isinstance(node, ast.AsyncFunctionDef),
                        parameters=self.parameters(node.args), returns=self.file.text(node.returns))
        self.result.nodes.append(item)
        self.result.edges.append({"type": "contains", "source": parent.node_id, "target": node_id,
                                  "resolution_status": "resolved", "analyzer": "ast",
                                  "evidence": self.evidence(node)})

        # Definition-time expressions belong to the enclosing scope, not the body.
        for decorator in node.decorator_list:
            self.visit_in_context(decorator, "definition_expression")
        if is_class:
            for expression in [*node.bases, *node.keywords]:
                self.visit_in_context(expression, "definition_expression")
        else:
            for expression in [*node.args.defaults, *node.args.kw_defaults]:
                if expression:
                    self.visit_in_context(expression, "definition_expression")
            if node.returns:
                self.visit_in_context(node.returns, "annotation")
            for argument in self.arguments(node.args):
                if argument.annotation:
                    self.visit_in_context(argument.annotation, "annotation")
        for parameter in getattr(node, "type_params", []):
            self.visit_in_context(parameter, "annotation")

        previous_conditional = self.conditional
        previous_context = self.context
        self.context = "class_body" if is_class else "function_body"
        self.scope = Scope("class" if is_class else "function", node_id, qualname, self.file, parent)
        self.conditional = 0
        for parameter in getattr(node, "type_params", []):
            self.bind(parameter.name, Binding("unsupported", parameter))
        if not is_class:
            for argument in self.arguments(node.args):
                self.bind(argument.arg, Binding("parameter", argument))
        for statement in node.body:
            self.visit(statement)
        self.scope = parent
        self.conditional = previous_conditional
        self.context = previous_context

    def visit_in_context(self, node, context):
        previous = self.context
        self.context = context
        self.visit(node)
        self.context = previous

    def visit_AnnAssign(self, node):
        self.visit(node.target)
        self.visit_in_context(node.annotation, "annotation")
        if node.value:
            self.visit(node.value)

    visit_FunctionDef = definition
    visit_AsyncFunctionDef = definition
    visit_ClassDef = definition

    @staticmethod
    def arguments(args: ast.arguments):
        return [*args.posonlyargs, *args.args, *([args.vararg] if args.vararg else []),
                *args.kwonlyargs, *([args.kwarg] if args.kwarg else [])]

    def parameters(self, args: ast.arguments):
        positional = [*args.posonlyargs, *args.args]
        defaults = dict(zip([a.arg for a in positional[len(positional) - len(args.defaults):]], args.defaults))
        defaults.update(zip([a.arg for a in args.kwonlyargs], args.kw_defaults))
        result = []
        for argument in self.arguments(args):
            kind = ("positional_only" if argument in args.posonlyargs else
                    "positional_or_keyword" if argument in args.args else
                    "var_positional" if argument is args.vararg else
                    "var_keyword" if argument is args.kwarg else "keyword_only")
            result.append({"name": argument.arg, "kind": kind,
                           "default": self.file.text(defaults.get(argument.arg)),
                           "annotation": self.file.text(argument.annotation)})
        return result

    def evidence(self, node):
        return {"file": self.file.relative, "line": node.lineno, "col": node.col_offset,
                "end_line": node.end_lineno, "end_col": node.end_col_offset}

    def visit_Call(self, node):
        self.result.calls.append((self.file, self.scope, node, self.context))
        self.generic_visit(node)

    def imports(self, node: ast.Import | ast.ImportFrom):
        for alias_index, alias in enumerate(node.names):
            record = {"scope": self.scope, "node": node, "name": alias.name, "alias": alias.asname,
                      "module": node.module if isinstance(node, ast.ImportFrom) else None,
                      "level": node.level if isinstance(node, ast.ImportFrom) else 0,
                      "kind": "from" if isinstance(node, ast.ImportFrom) else "import", "alias_index": alias_index}
            self.result.imports.append(record)
            if alias.name == "*":
                self.scope.wildcard = True
            else:
                name = alias.asname or (alias.name.split(".")[0] if isinstance(node, ast.Import) else alias.name)
                self.bind(name, Binding("import", node, import_record=record, conditional=bool(self.conditional)))

    visit_Import = imports
    visit_ImportFrom = imports

    def visit_Name(self, node):
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.bind(node.id, Binding("assignment", node))

    def visit_Attribute(self, node):
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            root = node.value
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name):
                self.bind(root.id, Binding("assignment", node))
        self.generic_visit(node)

    def visit_Global(self, node):
        self.scope.globals.update(node.names)

    def visit_Nonlocal(self, node):
        self.scope.nonlocals.update(node.names)

    def conditional_block(self, node):
        self.conditional += 1
        self.generic_visit(node)
        self.conditional -= 1

    visit_If = conditional_block
    visit_For = conditional_block
    visit_AsyncFor = conditional_block
    visit_While = conditional_block
    visit_Try = conditional_block
    visit_TryStar = conditional_block
    visit_With = conditional_block
    visit_AsyncWith = conditional_block
    visit_Match = conditional_block

    def visit_ExceptHandler(self, node):
        if node.name:
            self.bind(node.name, Binding("assignment", node))
        self.generic_visit(node)

    def visit_MatchAs(self, node):
        if node.name:
            self.bind(node.name, Binding("assignment", node))
        self.generic_visit(node)

    visit_MatchStar = visit_MatchAs

    def visit_MatchMapping(self, node):
        if node.rest:
            self.bind(node.rest, Binding("assignment", node))
        self.generic_visit(node)

    def visit_Lambda(self, node):
        for default in [*node.args.defaults, *node.args.kw_defaults]:
            if default:
                self.visit(default)
        parent = self.scope
        self.scope = Scope("lambda", parent.node_id, parent.qualified_name, self.file, parent)
        for argument in self.arguments(node.args):
            self.bind(argument.arg, Binding("parameter", argument))
        self.visit(node.body)
        self.scope = parent

    def comprehension(self, node):
        parent = self.scope
        self.visit(node.generators[0].iter)
        self.scope = Scope("comprehension", parent.node_id, parent.qualified_name, self.file, parent)
        for index, generator in enumerate(node.generators):
            if index:
                self.visit(generator.iter)
            self.visit(generator.target)
            for condition in generator.ifs:
                self.visit(condition)
        if isinstance(node, ast.DictComp):
            self.visit(node.key)
            self.visit(node.value)
        else:
            self.visit(node.elt)
        self.scope = parent

    visit_ListComp = comprehension
    visit_SetComp = comprehension
    visit_DictComp = comprehension
    visit_GeneratorExp = comprehension

    def visit_NamedExpr(self, node):
        previous = self.scope
        while self.scope.kind == "comprehension":
            self.scope = self.scope.parent
        self.visit(node.target)
        self.scope = previous
        self.visit(node.value)

    def visit_TypeAlias(self, node):
        # Python 3.12+: preserve alias binding while declining type-expression inference.
        self.visit(node.name)
        self.visit_in_context(node.value, "annotation")
