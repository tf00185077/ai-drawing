from __future__ import annotations

import sys

from launcher.runner import SubprocessRunner


def test_subprocess_runner_replaces_undecodable_output() -> None:
    result = SubprocessRunner().run(
        [
            sys.executable,
            "-c",
            "import os; os.write(1, bytes([0xFF]))",
        ]
    )

    assert result.returncode == 0
    assert result.stdout == "\N{REPLACEMENT CHARACTER}"
