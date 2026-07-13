# SPDX-License-Identifier: AGPL-3.0-or-later
"""Apply verified type annotations and docstrings via LibCST transformers."""

from __future__ import annotations

import libcst as cst

from llm_cst_refactorer.models import Suggestion


def _parse_annotation(text: str) -> cst.Annotation:
    """Parse a type annotation expression into an Annotation node."""
    cleaned = text.strip()
    module = cst.parse_module(f"def _f() -> {cleaned}:\n    pass\n")
    func = module.body[0]
    assert isinstance(func, cst.FunctionDef)
    assert func.returns is not None
    return func.returns


def _parse_param_annotation(text: str) -> cst.Annotation:
    cleaned = text.strip()
    module = cst.parse_module(f"def _f(x: {cleaned}):\n    pass\n")
    func = module.body[0]
    assert isinstance(func, cst.FunctionDef)
    param = func.params.params[0]
    assert param.annotation is not None
    return param.annotation


def _make_docstring_stmt(docstring: str) -> cst.SimpleStatementLine:
    """Create a docstring statement (triple-quoted)."""
    body = docstring.strip("\n")
    if '"""' in body and "'''" not in body:
        literal = f"'''{body}'''"
    else:
        safe = body.replace('"""', '\\"""')
        literal = f'"""{safe}"""'
    return cst.SimpleStatementLine(body=[cst.Expr(value=cst.SimpleString(literal))])


class AnnotationApplier(cst.CSTTransformer):
    """Insert annotations and docstrings for a specific qualified function name."""

    def __init__(self, qualified_name: str, suggestion: Suggestion) -> None:
        super().__init__()
        self._target = qualified_name
        self._suggestion = suggestion
        self._stack: list[str] = []
        self.applied = False

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        self._stack.append(node.name.value)
        return True

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        if self._stack and self._stack[-1] == original_node.name.value:
            self._stack.pop()
        return updated_node

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        self._stack.append(node.name.value)
        return True

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        result = self._maybe_apply(updated_node)
        if self._stack and self._stack[-1] == original_node.name.value:
            self._stack.pop()
        return result

    def _maybe_apply(self, updated: cst.FunctionDef) -> cst.FunctionDef:
        expected = ".".join(self._stack)
        if expected != self._target:
            return updated

        node = updated
        sug = self._suggestion

        param_map = sug.param_type_map()
        if param_map:
            node = node.with_changes(params=self._annotate_params(node.params, param_map))

        ret = sug.return_type_value()
        if ret and node.returns is None:
            node = node.with_changes(returns=_parse_annotation(ret))

        doc = sug.docstring_value()
        if doc and not self._has_docstring(node):
            node = self._insert_docstring(node, doc)

        self.applied = True
        return node

    def _annotate_params(self, params: cst.Parameters, types: dict[str, str]) -> cst.Parameters:
        def annotate_seq(seq: tuple[cst.Param, ...] | list[cst.Param]) -> list[cst.Param]:
            out: list[cst.Param] = []
            for param in seq:
                name = param.name.value
                if param.annotation is None and name in types:
                    out.append(param.with_changes(annotation=_parse_param_annotation(types[name])))
                else:
                    out.append(param)
            return out

        star_arg = params.star_arg
        if isinstance(star_arg, cst.Param) and star_arg.annotation is None:
            name = star_arg.name.value
            if name in types:
                star_arg = star_arg.with_changes(annotation=_parse_param_annotation(types[name]))

        star_kwarg = params.star_kwarg
        if star_kwarg is not None and star_kwarg.annotation is None:
            name = star_kwarg.name.value
            if name in types:
                star_kwarg = star_kwarg.with_changes(
                    annotation=_parse_param_annotation(types[name])
                )

        return params.with_changes(
            params=annotate_seq(list(params.params)),
            kwonly_params=annotate_seq(list(params.kwonly_params)),
            posonly_params=annotate_seq(list(params.posonly_params)),
            star_arg=star_arg,
            star_kwarg=star_kwarg,
        )

    @staticmethod
    def _has_docstring(node: cst.FunctionDef) -> bool:
        body = node.body
        if not isinstance(body, cst.IndentedBlock) or not body.body:
            return False
        first = body.body[0]
        if not isinstance(first, cst.SimpleStatementLine) or not first.body:
            return False
        stmt = first.body[0]
        return isinstance(stmt, cst.Expr) and isinstance(stmt.value, cst.BaseString)

    def _insert_docstring(self, node: cst.FunctionDef, docstring: str) -> cst.FunctionDef:
        body = node.body
        if not isinstance(body, cst.IndentedBlock):
            return node
        doc_stmt = _make_docstring_stmt(docstring)
        new_body = body.with_changes(body=(doc_stmt, *body.body))
        return node.with_changes(body=new_body)


def apply_suggestion(source: str, qualified_name: str, suggestion: Suggestion) -> str:
    """Return source with ``suggestion`` applied to ``qualified_name``."""
    module = cst.parse_module(source)
    transformer = AnnotationApplier(qualified_name, suggestion)
    updated = module.visit(transformer)
    return updated.code


def apply_suggestions(source: str, updates: dict[str, Suggestion]) -> str:
    """Apply multiple suggestions keyed by qualified name (sequential CST passes)."""
    current = source
    for qname, suggestion in updates.items():
        current = apply_suggestion(current, qname, suggestion)
    return current


def apply_init_none_return(source: str, qualified_name: str) -> str:
    """Locally annotate ``__init__`` return as ``None`` without an LLM call."""
    from llm_cst_refactorer.models import FieldSuggestion

    return apply_suggestion(
        source,
        qualified_name,
        Suggestion(return_type=FieldSuggestion(value="None", confidence=1.0)),
    )
