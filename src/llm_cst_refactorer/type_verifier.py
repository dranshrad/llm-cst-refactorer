# SPDX-License-Identifier: AGPL-3.0-or-later
"""Local mypy verification for candidate refactored source."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from llm_cst_refactorer.models import VerificationResult


def verify_source(
    source: str,
    *,
    python_executable: str | None = None,
    extra_args: list[str] | None = None,
    timeout: float = 60.0,
) -> VerificationResult:
    """Run mypy on ``source`` written to a temporary module.

    Uses ``--ignore-missing-imports`` so incomplete ambient types do not
    false-fail verification of newly inserted annotations.
    """
    py = python_executable or sys.executable
    args = [
        py,
        "-m",
        "mypy",
        "--no-incremental",
        "--ignore-missing-imports",
        "--pretty",
        "--show-error-codes",
        "--follow-imports=skip",
        "--no-error-summary",
    ]
    if extra_args:
        args.extend(extra_args)

    with tempfile.TemporaryDirectory(prefix="llm_cst_mypy_") as tmp:
        path = Path(tmp) / "candidate.py"
        path.write_text(source, encoding="utf-8")
        args.append(str(path))
        try:
            completed = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError:
            return VerificationResult(
                ok=False,
                errors="mypy is not available in the current environment.",
            )
        except subprocess.TimeoutExpired:
            return VerificationResult(ok=False, errors="mypy timed out while verifying candidate.")

        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        combined = "\n".join(part for part in (stdout, stderr) if part)

        if completed.returncode == 0:
            return VerificationResult(ok=True, errors="")
        return VerificationResult(ok=False, errors=combined or f"mypy exit {completed.returncode}")


def verify_file(path: Path, **kwargs: object) -> VerificationResult:
    """Verify an on-disk Python file with mypy."""
    source = path.read_text(encoding="utf-8")
    return verify_source(source, **kwargs)  # type: ignore[arg-type]
