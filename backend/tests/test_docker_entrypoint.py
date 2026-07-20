from pathlib import Path

import pytest

from scripts import docker_entrypoint
from scripts.docker_entrypoint import DATA_SUBDIRECTORIES, main, seed_directory


def test_seed_directory_copies_seed_into_empty_target(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    (source / "positive").mkdir(parents=True)
    target.mkdir()
    (source / "manifest.json").write_text("seed-manifest", encoding="utf-8")
    (source / "positive" / "portrait.json").write_text("seed-prompt", encoding="utf-8")

    assert seed_directory(source, target) is True
    assert (target / "manifest.json").read_text(encoding="utf-8") == "seed-manifest"
    assert (target / "positive" / "portrait.json").read_text(
        encoding="utf-8"
    ) == "seed-prompt"


def test_seed_directory_does_not_overwrite_nonempty_user_data(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "catalog.json").write_text("seed", encoding="utf-8")
    (target / "catalog.json").write_text("user", encoding="utf-8")

    assert seed_directory(source, target) is False
    assert (target / "catalog.json").read_text(encoding="utf-8") == "user"


def test_seed_directory_treats_nested_user_directory_as_nonempty(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "manifest.json").write_text("seed", encoding="utf-8")
    (target / "custom").mkdir()

    assert seed_directory(source, target) is False
    assert not (target / "manifest.json").exists()


def test_seed_directory_rolls_back_partial_copy_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "a.json").write_text("first", encoding="utf-8")
    (source / "b.json").write_text("second", encoding="utf-8")
    real_copy = docker_entrypoint.shutil.copy2

    def fail_second(source_path: Path, target_path: Path) -> None:
        if Path(source_path).name == "b.json":
            raise OSError("simulated copy failure")
        real_copy(source_path, target_path)

    monkeypatch.setattr(docker_entrypoint.shutil, "copy2", fail_second)

    with pytest.raises(OSError, match="simulated copy failure"):
        seed_directory(source, target)

    assert list(target.iterdir()) == []


def test_main_creates_persistent_directories_seeds_and_execs_command(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "manifest.json").write_text("seed", encoding="utf-8")
    executed: list[tuple[str, list[str]]] = []

    main(
        ["uvicorn", "app.main:app", "--port", "8000"],
        environ={
            "DATA_ROOT": str(data_root),
            "PROMPT_LIBRARY_SEED_DIR": str(seed),
        },
        exec_fn=lambda executable, args: executed.append((executable, args)),
    )

    assert all((data_root / name).is_dir() for name in DATA_SUBDIRECTORIES)
    assert (data_root / "prompt_library" / "manifest.json").read_text(
        encoding="utf-8"
    ) == "seed"
    assert executed == [
        (
            "uvicorn",
            ["uvicorn", "app.main:app", "--port", "8000"],
        )
    ]
