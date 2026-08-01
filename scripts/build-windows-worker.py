"""Build the Windows Worker directory and canonical ZIP without rewriting bytes."""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT_ROOT / "worker" / "windows"
DESTINATION = PROJECT_ROOT / "dist" / "AI-Drawing-NVIDIA-Worker"
ARCHIVE = PROJECT_ROOT / "dist" / "AI-Drawing-NVIDIA-Worker.zip"


def included(path: Path) -> bool:
    relative = path.relative_to(SOURCE)
    return "__pycache__" not in relative.parts and path.suffix not in {".pyc", ".pyo"}


def main() -> int:
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    DESTINATION.mkdir(parents=True)
    files = sorted((path for path in SOURCE.rglob("*") if path.is_file() and included(path)), key=lambda p: p.relative_to(SOURCE).as_posix())
    for source in files:
        relative = source.relative_to(SOURCE)
        destination = DESTINATION / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    ARCHIVE.unlink(missing_ok=True)
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED) as package:
        for source in files:
            name = source.relative_to(SOURCE).as_posix()
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            package.writestr(info, source.read_bytes())
    print(f"Built {ARCHIVE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
