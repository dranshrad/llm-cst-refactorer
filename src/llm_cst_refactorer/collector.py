# SPDX-License-Identifier: AGPL-3.0-or-later
"""Collect FunctionDef nodes that need annotations or docstrings."""

from __future__ import annotations

from dataclasses import dataclass

import libcst as cst
import libcst.matchers as m
from libcst.metadata import PositionProvider

from llm_cst_refactorer.models import FunctionContext, FunctionNeeds

SKIP_MARKERS = ("# noqa: llm-cst", "# llm-cst: skip")


@dataclass
class CollectedFunction:
    """A function that needs LLM-assisted annotation or documentation."""

    context: FunctionContext
    node: cst.FunctionDef
    skip: bool = False


@dataclass
class _Frame:
    name: str
    kind: str  # "class" | "function"


class AnnotationCollector(cst.CSTVisitor):
    """Visit a module and record under-annotated / undocumented functions."""

    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(
        self,
        *,
        source: str,
        file_path: str = "",
        types_only: bool = False,
        docs_only: bool = False,
    ) -> None:
        super().__init__()
        self._source = source
        self._source_lines = source.splitlines()
        self._file_path = file_path
        self._types_only = types_only
        self._docs_only = docs_only
        self._stack: list[_Frame] = []
        self._module_preamble: str = ""
        self.collected: list[CollectedFunction] = []

    def visit_Module(self, node: cst.Module) -> bool:
        preamble_parts: list[str] = []
        import_line = m.SimpleStatementLine(body=[m.Import() | m.ImportFrom()])
        for stmt in node.body:
            if m.matches(stmt, import_line) or m.matches(stmt, m.Import() | m.ImportFrom()):
                preamble_parts.append(self._code_for(stmt))
            elif preamble_parts:
                break
        self._module_preamble = "\n".join(preamble_parts)
        return True

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        self._stack.append(_Frame(node.name.value, "class"))
        return True

    def leave_ClassDef(self, original_node: cst.ClassDef) -> None:
        if self._stack and self._stack[-1].kind == "class":
            self._stack.pop()

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        self._record(node)
        self._stack.append(_Frame(node.name.value, "function"))
        return True

    def leave_FunctionDef(self, original_node: cst.FunctionDef) -> None:
        if self._stack and self._stack[-1].kind == "function":
            self._stack.pop()

    def _record(self, node: cst.FunctionDef) -> None:
        pos = self.get_metadata(PositionProvider, node, default=None)
        lineno = pos.start.line if pos is not None else 0
        if self._is_skipped(lineno):
            return

        name = node.name.value
        is_async = node.asynchronous is not None
        is_method = any(frame.kind == "class" for frame in self._stack)
        qualified = ".".join([*(f.name for f in self._stack), name])

        params = (
            list(node.params.posonly_params)
            + list(node.params.params)
            + list(node.params.kwonly_params)
        )
        if node.params.star_arg and isinstance(node.params.star_arg, cst.Param):
            params.append(node.params.star_arg)
        if node.params.star_kwarg:
            params.append(node.params.star_kwarg)

        param_names: list[str] = []
        missing_param_names: list[str] = []
        for idx, param in enumerate(params):
            pname = param.name.value
            param_names.append(pname)
            if pname in {"self", "cls"} and idx == 0 and is_method:
                continue
            if param.annotation is None:
                missing_param_names.append(pname)

        has_return = node.returns is not None
        needs_return = not has_return and name != "__init__"
        has_docstring = _has_docstring(node)
        needs_docstring = not has_docstring

        needs = FunctionNeeds(
            needs_params=bool(missing_param_names),
            needs_return=needs_return,
            needs_docstring=needs_docstring,
        )

        if self._types_only:
            needs = FunctionNeeds(
                needs_params=needs.needs_params,
                needs_return=needs.needs_return,
                needs_docstring=False,
            )
        if self._docs_only:
            needs = FunctionNeeds(
                needs_params=False,
                needs_return=False,
                needs_docstring=needs_docstring,
            )

        if not needs.any:
            return

        class_context = None
        class_frames = [f for f in self._stack if f.kind == "class"]
        if class_frames:
            class_context = class_frames[-1].name

        ctx = FunctionContext(
            qualified_name=qualified,
            function_source=self._code_for(node),
            module_preamble=self._module_preamble,
            class_context=class_context,
            param_names=param_names,
            missing_param_names=missing_param_names,
            has_return_annotation=has_return,
            has_docstring=has_docstring,
            is_async=is_async,
            is_method=is_method,
            needs=needs,
            file_path=self._file_path,
            lineno=lineno,
        )
        self.collected.append(CollectedFunction(context=ctx, node=node))

    def _is_skipped(self, lineno: int) -> bool:
        if lineno <= 0:
            return False
        indices = [lineno - 1]
        if lineno - 2 >= 0:
            indices.append(lineno - 2)
        for idx in indices:
            if 0 <= idx < len(self._source_lines):
                line = self._source_lines[idx]
                if any(marker in line for marker in SKIP_MARKERS):
                    return True
        return False

    def _code_for(self, node: cst.CSTNode) -> str:
        return cst.Module([]).code_for_node(node)


def _has_docstring(node: cst.FunctionDef) -> bool:
    body = node.body
    if not isinstance(body, cst.IndentedBlock) or not body.body:
        return False
    first = body.body[0]
    if not isinstance(first, cst.SimpleStatementLine) or not first.body:
        return False
    stmt = first.body[0]
    return isinstance(stmt, cst.Expr) and isinstance(stmt.value, cst.BaseString)


def collect_functions(
    source: str,
    *,
    file_path: str = "",
    types_only: bool = False,
    docs_only: bool = False,
) -> list[CollectedFunction]:
    """Parse ``source`` and return functions that need work."""
    module = cst.parse_module(source)
    wrapper = cst.MetadataWrapper(module)
    collector = AnnotationCollector(
        source=source,
        file_path=file_path,
        types_only=types_only,
        docs_only=docs_only,
    )
    wrapper.visit(collector)
    return collector.collected
