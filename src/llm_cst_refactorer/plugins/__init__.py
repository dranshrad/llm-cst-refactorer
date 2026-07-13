# SPDX-License-Identifier: AGPL-3.0-or-later
"""Plugin API for semantic refactor tasks."""

from llm_cst_refactorer.plugins.base import RefactorPlugin
from llm_cst_refactorer.plugins.factory import create_plugin, create_plugins
from llm_cst_refactorer.plugins.init_return_none import InitReturnNonePlugin
from llm_cst_refactorer.plugins.typing_docstring import TypingDocstringPlugin

__all__ = [
    "InitReturnNonePlugin",
    "RefactorPlugin",
    "TypingDocstringPlugin",
    "create_plugin",
    "create_plugins",
]
