from __future__ import annotations

import argparse
from collections.abc import Sequence

from .models import LauncherCommand


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI Drawing launcher")
    parser.add_argument(
        "command",
        nargs="?",
        choices=[command.value for command in LauncherCommand],
        default=LauncherCommand.SETUP.value,
    )
    parser.parse_args(argv)
    return 0
