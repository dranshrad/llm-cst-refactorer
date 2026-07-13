# SPDX-License-Identifier: AGPL-3.0-or-later
"""Lightweight repository index for prompt context slices."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import libcst as cst
import libcst.matchers as m

from llm_cst_refactorer.semantic import RepoContextSlice, SemanticFunction


@dataclass
class FileSymbols:
    """Top-level symbols discovered in a single module."""

    path: Path
    imports: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    methods: dict[str, list[str]] = field(default_factory=dict)
    annotated_params: int = 0
    total_params: int = 0
    uses_optional: int = 0
    uses_pipe_none: int = 0
    source: str = ""


class RepoIndex:
    """Project-wide import/symbol index built before LLM calls."""

    def __init__(self, files: list[Path]) -> None:
        self.root = files[0].parent if files else Path(".")
        self.files: dict[str, FileSymbols] = {}
        for path in files:
            try:
                source = path.read_text(encoding="utf-8")
            except OSError:
                continue
            try:
                module = cst.parse_module(source)
            except cst.ParserSyntaxError:
                continue
            self.files[str(path.resolve())] = _extract_file_symbols(path, source, module)

    def slice_for(self, fn: SemanticFunction) -> RepoContextSlice:
        """Build a truncated context slice for ``fn``."""
        key = str(Path(fn.file_path).resolve()) if fn.file_path else ""
        info = self.files.get(key)
        if info is None and fn.file_path:
            # try as-is
            info = self.files.get(fn.file_path)

        neighboring: list[str] = []
        imported: list[str] = []
        conventions: list[str] = []
        related: list[str] = []
        preamble = ""

        if info is not None:
            imported = list(info.imports)[:40]
            preamble = "\n".join(info.imports[:20])
            if fn.is_method and fn.repo_context.class_context:
                class_name = fn.repo_context.class_context
                neighboring = [
                    f"{class_name}.{mname}"
                    for mname in info.methods.get(class_name, [])
                    if f"{class_name}.{mname}" != fn.qualified_name
                ][:12]
            else:
                neighboring = [name for name in info.functions if name != fn.qualified_name][:12]
                neighboring.extend(info.classes[:8])

            density = info.annotated_params / info.total_params if info.total_params else 0.0
            conventions.append(f"annotation_density={density:.2f}")
            if info.uses_pipe_none >= info.uses_optional:
                conventions.append("prefer_union_none=X | None")
            else:
                conventions.append("prefer_optional=Optional[X]")

        # Related files that import similar names or share basename stem
        stem = Path(fn.file_path).stem if fn.file_path else ""
        for path_str, other in self.files.items():
            if path_str == key:
                continue
            other_stem = Path(path_str).stem
            same_stem = bool(stem) and (stem in other_stem or other_stem in stem)
            imports_stem = any(imp.split(".")[-1] == stem for imp in other.imports)
            if same_stem or imports_stem:
                related.append(path_str)
            if len(related) >= 5:
                break

        return RepoContextSlice(
            module_preamble=preamble or fn.repo_context.module_preamble,
            class_context=fn.repo_context.class_context,
            neighboring_symbols=neighboring,
            imported_names=imported,
            convention_hints=conventions,
            related_files=[str(Path(p).name) for p in related],
        )

    def attach(self, fn: SemanticFunction) -> SemanticFunction:
        """Return ``fn`` with repo_context filled from the index."""
        slice_ = self.slice_for(fn)
        # Preserve class_context / preamble if index missed the file
        if not slice_.module_preamble and fn.repo_context.module_preamble:
            slice_ = slice_.model_copy(update={"module_preamble": fn.repo_context.module_preamble})
        if slice_.class_context is None and fn.repo_context.class_context:
            slice_ = slice_.model_copy(update={"class_context": fn.repo_context.class_context})
        return fn.model_copy(update={"repo_context": slice_}).with_fingerprint()


def _extract_file_symbols(path: Path, source: str, module: cst.Module) -> FileSymbols:
    info = FileSymbols(path=path, source=source)
    for stmt in module.body:
        if m.matches(stmt, m.SimpleStatementLine(body=[m.Import() | m.ImportFrom()])):
            info.imports.append(cst.Module([]).code_for_node(stmt).strip())
        elif isinstance(stmt, cst.FunctionDef):
            info.functions.append(stmt.name.value)
            _count_annotations(stmt, info)
        elif isinstance(stmt, cst.ClassDef):
            cname = stmt.name.value
            info.classes.append(cname)
            methods: list[str] = []
            for item in stmt.body.body if isinstance(stmt.body, cst.IndentedBlock) else []:
                if isinstance(item, cst.FunctionDef):
                    methods.append(item.name.value)
                    _count_annotations(item, info)
            info.methods[cname] = methods

    # Convention scanners on full source
    info.uses_optional = source.count("Optional[")
    info.uses_pipe_none = source.count("| None")
    return info


def _count_annotations(node: cst.FunctionDef, info: FileSymbols) -> None:
    params = (
        list(node.params.posonly_params)
        + list(node.params.params)
        + list(node.params.kwonly_params)
    )
    for param in params:
        if param.name.value in {"self", "cls"}:
            continue
        info.total_params += 1
        if param.annotation is not None:
            info.annotated_params += 1
