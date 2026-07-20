from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path


DATA_SUBDIRECTORIES = (
    "database",
    "outputs",
    "gallery",
    "lora_train",
    "prompt_library",
    "logs",
)


def seed_directory(source: Path, target: Path) -> bool:
    """Copy packaged defaults only when the user's target is completely empty."""
    source = Path(source)
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    if any(target.iterdir()):
        return False
    created: list[Path] = []
    try:
        for child in source.iterdir():
            destination = target / child.name
            created.append(destination)
            if child.is_dir():
                shutil.copytree(child, destination)
            else:
                shutil.copy2(child, destination)
    except BaseException:
        for destination in reversed(created):
            if destination.is_dir():
                shutil.rmtree(destination, ignore_errors=True)
            else:
                destination.unlink(missing_ok=True)
        raise
    return True


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] = os.environ,
    exec_fn: Callable[[str, list[str]], object] = os.execvp,
) -> None:
    command = list(sys.argv[1:] if argv is None else argv)
    if not command:
        raise SystemExit("container command is required")

    data_root = Path(environ.get("DATA_ROOT", "/data"))
    for directory in DATA_SUBDIRECTORIES:
        (data_root / directory).mkdir(parents=True, exist_ok=True)

    seed_directory(
        Path(
            environ.get(
                "PROMPT_LIBRARY_SEED_DIR",
                "/opt/ai-drawing-seed/prompt_library",
            )
        ),
        data_root / "prompt_library",
    )
    exec_fn(command[0], command)


if __name__ == "__main__":
    main()
