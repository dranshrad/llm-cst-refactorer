# SPDX-License-Identifier: AGPL-3.0-or-later
"""Collect FunctionDef nodes into SemanticFunction IR."""

from __future__ import annotations

from dataclasses import dataclass

import libcst as cst
import libcst.matchers as m
from libcst.metadata import PositionProvider

from llm_cst_refactorer.models import FunctionNeeds
from llm_cst_refactorer.semantic import ParamInfo, RepoContextSlice, SemanticFunction

SKIP_MARKERS = ("# noqa: llm-cst", "# llm-cst: skip")


@dataclass
class CollectedFunction:
    """A function that needs LLM-assisted annotation or documentation."""

    semantic: SemanticFunction
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

        raw_params = (
            list(node.params.posonly_params)
            + list(node.params.params)
            + list(node.params.kwonly_params)
        )
        if node.params.star_arg and isinstance(node.params.star_arg, cst.Param):
            raw_params.append(node.params.star_arg)
        if node.params.star_kwarg:
            raw_params.append(node.params.star_kwarg)

        params: list[ParamInfo] = []
        missing_param_names: list[str] = []
        for idx, param in enumerate(raw_params):
            pname = param.name.value
            is_self = pname in {"self", "cls"} and idx == 0 and is_method
            ann = None
            if param.annotation is not None:
                ann = self._code_for(param.annotation.annotation).strip()
            info = ParamInfo(
                name=pname,
                annotation=ann,
                has_default=param.default is not None,
                is_self_or_cls=is_self,
            )
            params.append(info)
            if not is_self and ann is None:
                missing_param_names.append(pname)

        return_ann = None
        if node.returns is not None:
            return_ann = self._code_for(node.returns.annotation).strip()

        has_return = return_ann is not None
        needs_return = not has_return
        docstring = _extract_docstring(node)
        needs_docstring = docstring is None

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

        semantic = SemanticFunction(
            qualified_name=qualified,
            file_path=self._file_path,
            lineno=lineno,
            is_async=is_async,
            is_method=is_method,
            source=self._code_for(node),
            params=params,
            return_annotation=return_ann,
            docstring=docstring,
            needs=needs,
            repo_context=RepoContextSlice(
                module_preamble=self._module_preamble,
                class_context=class_context,
            ),
        ).with_fingerprint()
        self.collected.append(CollectedFunction(semantic=semantic, node=node))

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


def _extract_docstring(node: cst.FunctionDef) -> str | None:
    body = node.body
    if not isinstance(body, cst.IndentedBlock) or not body.body:
        return None
    first = body.body[0]
    if not isinstance(first, cst.SimpleStatementLine) or not first.body:
        return None
    stmt = first.body[0]
    if isinstance(stmt, cst.Expr) and isinstance(stmt.value, cst.BaseString):
        return cst.Module([]).code_for_node(stmt.value).strip().strip("\"'")
    return None


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
