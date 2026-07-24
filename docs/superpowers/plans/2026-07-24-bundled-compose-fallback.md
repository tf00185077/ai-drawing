# Bundled Docker Compose Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let anyone with a running Docker daemon complete `setup`, even when their system Docker Compose is too old, v1-only, or missing — by falling back to a pinned, privately-cached standalone compose binary.

**Architecture:** `preflight()` resolves a `ComposeRuntime` (an invocation prefix). If the system `docker compose` meets the floor it is used unchanged; otherwise a pinned standalone binary is downloaded to a private cache, checksum-verified, and invoked by absolute path. The resolved invocation prefix threads through the single `compose_command()` entry point that every compose action already funnels through. The bundled binary never touches PATH or `~/.docker`.

**Tech Stack:** Python 3.12 stdlib (`urllib.request`, `hashlib`, `dataclasses`), pytest. No new third-party dependencies.

## Global Constraints

- Compose floor for "system compose is good enough": `COMPOSE_MINIMUM = (2, 24, 0)` (existing, unchanged).
- Pinned fallback version: `COMPOSE_BUNDLED_VERSION = "2.32.4"` (must be ≥ floor).
- Bundled binary is **private**: cache only, invoked by absolute path. Never write `~/.docker/cli-plugins/`, never modify PATH, never create a global `docker-compose` alias.
- Download only from the official GitHub release; execute only after the pinned SHA256 matches.
- All new `DockerError`s carry a Traditional-Chinese `message` and `hint`, matching the existing style in `scripts/launcher/docker.py`.
- Read-only commands (`status`, `dry-run`) must never trigger a download (`allow_download=False`); a cached bundled binary may still be used.
- `HostInfo` fields: `system` ∈ {`"Windows"`,`"Darwin"`,`"Linux"`}, `machine` (e.g. `"AMD64"`, `"x86_64"`, `"arm64"`, `"aarch64"`), `home: Path`.
- All subprocess calls go through the injected `Runner`; all downloads through an injected `downloader` — never call the network directly in a testable function.

---

### Task 1: Pin the bundled version, release URL, and per-asset SHA256 table

**Files:**
- Modify: `scripts/launcher/constants.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `COMPOSE_BUNDLED_VERSION: str = "2.32.4"`
  - `COMPOSE_RELEASE_URL: str = "https://github.com/docker/compose/releases/download"`
  - `COMPOSE_ASSET_SHA256: dict[str, str]` — keys are asset filenames (e.g. `"docker-compose-linux-x86_64"`), values are lowercase hex SHA256.

- [ ] **Step 1: Fetch the real checksums from the official release**

The SHA256 values MUST be real — do not invent them. Each release asset has a sibling `.sha256` file. Run:

```bash
for asset in \
  docker-compose-linux-x86_64 \
  docker-compose-linux-aarch64 \
  docker-compose-darwin-x86_64 \
  docker-compose-darwin-aarch64 \
  docker-compose-windows-x86_64.exe \
  docker-compose-windows-aarch64.exe; do
  printf '%s = ' "$asset"
  curl -sL "https://github.com/docker/compose/releases/download/v2.32.4/${asset}.sha256"
done
```

Each line prints like `<sha256>  docker-compose-linux-x86_64`. Copy the 64-char hex (first field) for each asset. If any asset 404s (a platform not published for this version), omit that key — Task 2's mapping will raise `COMPOSE_BUNDLED_UNSUPPORTED_ARCH` for it.

- [ ] **Step 2: Add the constants**

Append to `scripts/launcher/constants.py` (keep `COMPOSE_MINIMUM` as-is):

```python
COMPOSE_BUNDLED_VERSION = "2.32.4"
COMPOSE_RELEASE_URL = "https://github.com/docker/compose/releases/download"
COMPOSE_ASSET_SHA256 = {
    "docker-compose-linux-x86_64": "<fill-from-step-1>",
    "docker-compose-linux-aarch64": "<fill-from-step-1>",
    "docker-compose-darwin-x86_64": "<fill-from-step-1>",
    "docker-compose-darwin-aarch64": "<fill-from-step-1>",
    "docker-compose-windows-x86_64.exe": "<fill-from-step-1>",
    "docker-compose-windows-aarch64.exe": "<fill-from-step-1>",
}
```

- [ ] **Step 3: Sanity-check the values**

Run:

```bash
cd scripts && python -c "from launcher import constants as c; assert c.COMPOSE_BUNDLED_VERSION >= '2.24.0'; assert all(len(v)==64 and all(ch in '0123456789abcdef' for ch in v) for v in c.COMPOSE_ASSET_SHA256.values()), 'checksums must be 64-char lowercase hex'; print('ok', len(c.COMPOSE_ASSET_SHA256), 'assets')"
```
Expected: `ok 6 assets` (or fewer if any asset was legitimately unavailable).

- [ ] **Step 4: Commit**

```bash
git add scripts/launcher/constants.py
git commit -m "feat(launcher): pin bundled docker compose version and asset checksums"
```

---

### Task 2: Platform/arch → asset name, download URL, and private cache path

**Files:**
- Modify: `scripts/launcher/docker.py` (add functions near the top, after imports)
- Test: `scripts/tests/test_docker_launcher.py`

**Interfaces:**
- Consumes: `COMPOSE_BUNDLED_VERSION`, `COMPOSE_RELEASE_URL`, `COMPOSE_ASSET_SHA256` (Task 1); `HostInfo`; `DockerError`.
- Produces:
  - `normalize_arch(machine: str) -> str` → `"x86_64"` or `"aarch64"`; raises `DockerError("COMPOSE_BUNDLED_UNSUPPORTED_ARCH", ...)`.
  - `compose_asset_name(host: HostInfo) -> str` (includes `.exe` on Windows).
  - `compose_download_url(host: HostInfo) -> str`.
  - `compose_expected_sha256(host: HostInfo) -> str`; raises `COMPOSE_BUNDLED_UNSUPPORTED_ARCH` if the asset has no pinned checksum.
  - `compose_cache_path(host: HostInfo, *, cache_root: Path | None = None) -> Path` → `<root>/ai-drawing/compose/<version>/docker-compose[.exe]`.

- [ ] **Step 1: Write the failing tests**

Add to `scripts/tests/test_docker_launcher.py`:

```python
from launcher.docker import (
    compose_asset_name,
    compose_cache_path,
    compose_download_url,
    compose_expected_sha256,
    normalize_arch,
)
from launcher.platforms import detect_host
from launcher import constants


@pytest.mark.parametrize(
    ("machine", "expected"),
    [("x86_64", "x86_64"), ("AMD64", "x86_64"), ("arm64", "aarch64"), ("aarch64", "aarch64")],
)
def test_normalize_arch_maps_known_machines(machine, expected):
    assert normalize_arch(machine) == expected


def test_normalize_arch_rejects_unknown():
    with pytest.raises(DockerError) as raised:
        normalize_arch("mips")
    assert raised.value.code == "COMPOSE_BUNDLED_UNSUPPORTED_ARCH"
    assert raised.value.hint


def test_compose_asset_name_and_url_for_windows():
    host = detect_host(system="Windows", machine="AMD64", home=Path("C:/Users/x"))
    assert compose_asset_name(host) == "docker-compose-windows-x86_64.exe"
    assert compose_download_url(host) == (
        f"{constants.COMPOSE_RELEASE_URL}/v{constants.COMPOSE_BUNDLED_VERSION}"
        "/docker-compose-windows-x86_64.exe"
    )


def test_compose_asset_name_for_linux_arm():
    host = detect_host(system="Linux", machine="aarch64", home=Path("/home/x"))
    assert compose_asset_name(host) == "docker-compose-linux-aarch64"


def test_compose_cache_path_is_private_and_versioned(tmp_path):
    host = detect_host(system="Linux", machine="x86_64", home=Path("/home/x"))
    path = compose_cache_path(host, cache_root=tmp_path)
    assert path == tmp_path / "ai-drawing" / "compose" / constants.COMPOSE_BUNDLED_VERSION / "docker-compose"
    win = detect_host(system="Windows", machine="AMD64", home=Path("C:/Users/x"))
    assert compose_cache_path(win, cache_root=tmp_path).name == "docker-compose.exe"


def test_compose_expected_sha256_present_for_supported_asset():
    host = detect_host(system="Linux", machine="x86_64", home=Path("/home/x"))
    assert len(compose_expected_sha256(host)) == 64
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd scripts && python -m pytest tests/test_docker_launcher.py -k "arch or asset or cache or sha256" -v`
Expected: FAIL with `ImportError` / `cannot import name`.

- [ ] **Step 3: Implement**

Add near the top of `scripts/launcher/docker.py` (after the existing imports; add `import hashlib`, `import os` to the import block, and `from .constants import COMPOSE_BUNDLED_VERSION, COMPOSE_RELEASE_URL, COMPOSE_ASSET_SHA256` alongside the existing `from .constants import COMPOSE_MINIMUM`; import `HostInfo` with `from .models import HostInfo`):

```python
def normalize_arch(machine: str) -> str:
    key = machine.lower()
    if key in {"x86_64", "amd64"}:
        return "x86_64"
    if key in {"aarch64", "arm64"}:
        return "aarch64"
    raise DockerError(
        "COMPOSE_BUNDLED_UNSUPPORTED_ARCH",
        f"沒有對應此架構（{machine}）的自帶 Docker Compose。",
        "請改用系統套件管理員安裝 Docker Compose v2.24 以上版本。",
    )


_COMPOSE_OS = {"Windows": "windows", "Darwin": "darwin", "Linux": "linux"}


def compose_asset_name(host: HostInfo) -> str:
    os_name = _COMPOSE_OS.get(host.system)
    if os_name is None:
        raise DockerError(
            "COMPOSE_BUNDLED_UNSUPPORTED_ARCH",
            f"沒有對應此作業系統（{host.system}）的自帶 Docker Compose。",
            "請改用系統套件管理員安裝 Docker Compose v2.24 以上版本。",
        )
    arch = normalize_arch(host.machine)
    suffix = ".exe" if os_name == "windows" else ""
    return f"docker-compose-{os_name}-{arch}{suffix}"


def compose_download_url(host: HostInfo) -> str:
    return f"{COMPOSE_RELEASE_URL}/v{COMPOSE_BUNDLED_VERSION}/{compose_asset_name(host)}"


def compose_expected_sha256(host: HostInfo) -> str:
    asset = compose_asset_name(host)
    digest = COMPOSE_ASSET_SHA256.get(asset)
    if digest is None:
        raise DockerError(
            "COMPOSE_BUNDLED_UNSUPPORTED_ARCH",
            f"沒有為 {asset} 釘選的校驗碼。",
            "請改用系統套件管理員安裝 Docker Compose v2.24 以上版本。",
        )
    return digest


def _default_cache_root(host: HostInfo) -> Path:
    if host.system == "Windows":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("USERPROFILE")
        return Path(base) if base else host.home
    xdg = os.environ.get("XDG_CACHE_HOME")
    return Path(xdg) if xdg else host.home / ".cache"


def _bundled_filename(host: HostInfo) -> str:
    return "docker-compose.exe" if host.system == "Windows" else "docker-compose"


def compose_cache_path(host: HostInfo, *, cache_root: Path | None = None) -> Path:
    root = cache_root if cache_root is not None else _default_cache_root(host)
    return Path(root) / "ai-drawing" / "compose" / COMPOSE_BUNDLED_VERSION / _bundled_filename(host)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd scripts && python -m pytest tests/test_docker_launcher.py -k "arch or asset or cache or sha256" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/launcher/docker.py scripts/tests/test_docker_launcher.py
git commit -m "feat(launcher): map platform to bundled compose asset and private cache path"
```

---

### Task 3: Download-and-verify helper

**Files:**
- Modify: `scripts/launcher/docker.py`
- Test: `scripts/tests/test_docker_launcher.py`

**Interfaces:**
- Consumes: `DockerError`; `hashlib`, `os` (imported in Task 2).
- Produces:
  - Type alias `Downloader = Callable[[str, Path], None]` (writes URL bytes to the given path).
  - `urlopen_download(url: str, dest: Path) -> None` — default `Downloader` using `urllib.request.urlopen`.
  - `_download_compose(url: str, dest: Path, expected_sha256: str, *, downloader: Downloader) -> None` — downloads to a `.partial` sibling, verifies SHA256, sets `0o755` on POSIX, atomically replaces `dest`. Raises `COMPOSE_DOWNLOAD_FAILED` or `COMPOSE_CHECKSUM_MISMATCH`, cleaning up the partial file on failure.

- [ ] **Step 1: Write the failing tests**

Add to `scripts/tests/test_docker_launcher.py`:

```python
import hashlib
from launcher.docker import _download_compose


def test_download_compose_verifies_checksum_and_replaces(tmp_path):
    dest = tmp_path / "docker-compose"
    payload = b"#!/bin/sh\necho compose\n"
    digest = hashlib.sha256(payload).hexdigest()

    def fake_downloader(url, path):
        path.write_bytes(payload)

    _download_compose("https://example/compose", dest, digest, downloader=fake_downloader)
    assert dest.read_bytes() == payload
    assert not dest.with_name("docker-compose.partial").exists()


def test_download_compose_rejects_bad_checksum_and_cleans_up(tmp_path):
    dest = tmp_path / "docker-compose"

    def fake_downloader(url, path):
        path.write_bytes(b"tampered")

    with pytest.raises(DockerError) as raised:
        _download_compose("https://example/compose", dest, "0" * 64, downloader=fake_downloader)
    assert raised.value.code == "COMPOSE_CHECKSUM_MISMATCH"
    assert not dest.exists()
    assert not dest.with_name("docker-compose.partial").exists()


def test_download_compose_reports_download_failure(tmp_path):
    dest = tmp_path / "docker-compose"

    def failing_downloader(url, path):
        raise OSError("network down")

    with pytest.raises(DockerError) as raised:
        _download_compose("https://example/compose", dest, "0" * 64, downloader=failing_downloader)
    assert raised.value.code == "COMPOSE_DOWNLOAD_FAILED"
    assert not dest.with_name("docker-compose.partial").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd scripts && python -m pytest tests/test_docker_launcher.py -k download_compose -v`
Expected: FAIL with `cannot import name '_download_compose'`.

- [ ] **Step 3: Implement**

Add to `scripts/launcher/docker.py` (the `Callable` import already exists in the module's typing imports):

```python
Downloader = Callable[[str, Path], None]


def urlopen_download(url: str, dest: Path) -> None:
    with urlopen(url, timeout=60) as response:
        data = response.read()
    dest.write_bytes(data)


def _download_compose(
    url: str,
    dest: Path,
    expected_sha256: str,
    *,
    downloader: Downloader,
) -> None:
    partial = dest.with_name(dest.name + ".partial")
    partial.unlink(missing_ok=True)
    try:
        downloader(url, partial)
    except OSError as error:
        partial.unlink(missing_ok=True)
        raise DockerError(
            "COMPOSE_DOWNLOAD_FAILED",
            "自帶 Docker Compose 下載失敗。",
            "請確認網路與 github.com 可連線後重試；或安裝系統 Docker Compose v2.24 以上。",
        ) from error
    digest = hashlib.sha256(partial.read_bytes()).hexdigest()
    if digest != expected_sha256:
        partial.unlink(missing_ok=True)
        raise DockerError(
            "COMPOSE_CHECKSUM_MISMATCH",
            "自帶 Docker Compose 的校驗碼不符，已刪除下載檔。",
            "請重試下載；若持續失敗，請改安裝系統 Docker Compose v2.24 以上。",
        )
    if os.name != "nt":
        partial.chmod(0o755)
    os.replace(partial, dest)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd scripts && python -m pytest tests/test_docker_launcher.py -k download_compose -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/launcher/docker.py scripts/tests/test_docker_launcher.py
git commit -m "feat(launcher): add checksum-verified compose download helper"
```

---

### Task 4: `ComposeRuntime` and `resolve_compose_runtime`

**Files:**
- Modify: `scripts/launcher/docker.py`
- Test: `scripts/tests/test_docker_launcher.py`

**Interfaces:**
- Consumes: `_parse_compose_version` (existing), `_run` (existing), `compose_cache_path`, `compose_download_url`, `compose_expected_sha256`, `_download_compose`, `urlopen_download` (Tasks 2–3); `COMPOSE_MINIMUM`.
- Produces:
  - `@dataclass(frozen=True) class ComposeRuntime: invocation: tuple[str, ...]; version: tuple[int, int, int]; source: str` (`source` ∈ {`"system"`,`"bundled"`}).
  - `resolve_compose_runtime(host, runner, *, allow_download=True, downloader=None, cache_root=None) -> ComposeRuntime`.

- [ ] **Step 1: Write the failing tests**

Add to `scripts/tests/test_docker_launcher.py`:

```python
from launcher.docker import ComposeRuntime, resolve_compose_runtime

LINUX = detect_host(system="Linux", machine="x86_64", home=Path("/home/x"))


def test_resolve_uses_system_compose_when_new_enough(tmp_path):
    runner = FakeRunner((result(stdout="2.29.7\n"),))
    downloads = []
    runtime = resolve_compose_runtime(
        LINUX, runner, cache_root=tmp_path,
        downloader=lambda url, path: downloads.append(url),
    )
    assert runtime == ComposeRuntime(("docker", "compose"), (2, 29, 7), "system")
    assert downloads == []  # system was good enough — nothing downloaded


def test_resolve_downloads_bundled_when_system_too_old(tmp_path):
    payload = b"bundled-compose"
    digest = hashlib.sha256(payload).hexdigest()
    # system reports 2.20.2 (too old) -> then bundled `version --short` reports 2.32.4
    runner = FakeRunner((result(stdout="2.20.2\n"), result(stdout="2.32.4\n")))
    seen = {}

    def fake_downloader(url, path):
        seen["url"] = url
        path.write_bytes(payload)

    import launcher.docker as dockermod
    original = dockermod.COMPOSE_ASSET_SHA256["docker-compose-linux-x86_64"]
    dockermod.COMPOSE_ASSET_SHA256["docker-compose-linux-x86_64"] = digest
    try:
        runtime = resolve_compose_runtime(
            LINUX, runner, cache_root=tmp_path, downloader=fake_downloader
        )
    finally:
        dockermod.COMPOSE_ASSET_SHA256["docker-compose-linux-x86_64"] = original
    assert runtime.source == "bundled"
    assert runtime.version == (2, 32, 4)
    assert runtime.invocation == (str(compose_cache_path(LINUX, cache_root=tmp_path)),)
    assert "docker-compose-linux-x86_64" in seen["url"]


def test_resolve_uses_cached_bundled_without_download(tmp_path):
    path = compose_cache_path(LINUX, cache_root=tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"cached")
    # system too old, then cached bundled `version --short` reports 2.32.4
    runner = FakeRunner((result(stdout="2.10.0\n"), result(stdout="2.32.4\n")))

    def forbidden(url, p):
        raise AssertionError("must not download when cache is present")

    runtime = resolve_compose_runtime(
        LINUX, runner, cache_root=tmp_path, downloader=forbidden
    )
    assert runtime.source == "bundled"
    assert runtime.invocation == (str(path),)


def test_resolve_read_only_never_downloads(tmp_path):
    runner = FakeRunner((result(stdout="2.10.0\n"),))  # too old, no cache

    def forbidden(url, p):
        raise AssertionError("read-only must not download")

    with pytest.raises(DockerError) as raised:
        resolve_compose_runtime(
            LINUX, runner, allow_download=False, cache_root=tmp_path, downloader=forbidden
        )
    assert raised.value.code == "COMPOSE_UNAVAILABLE"


def test_resolve_handles_missing_system_compose(tmp_path):
    # `docker compose version` fails (v1-only / no plugin) -> falls back to bundled
    payload = b"bundled"
    digest = hashlib.sha256(payload).hexdigest()
    runner = FakeRunner((result(1, stderr="unknown command"), result(stdout="2.32.4\n")))
    import launcher.docker as dockermod
    original = dockermod.COMPOSE_ASSET_SHA256["docker-compose-linux-x86_64"]
    dockermod.COMPOSE_ASSET_SHA256["docker-compose-linux-x86_64"] = digest
    try:
        runtime = resolve_compose_runtime(
            LINUX, runner, cache_root=tmp_path,
            downloader=lambda url, path: path.write_bytes(payload),
        )
    finally:
        dockermod.COMPOSE_ASSET_SHA256["docker-compose-linux-x86_64"] = original
    assert runtime.source == "bundled"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd scripts && python -m pytest tests/test_docker_launcher.py -k resolve -v`
Expected: FAIL with `cannot import name 'resolve_compose_runtime'`.

- [ ] **Step 3: Implement**

Add to `scripts/launcher/docker.py` (place `ComposeRuntime` near `DockerPreflight`):

```python
@dataclass(frozen=True)
class ComposeRuntime:
    invocation: tuple[str, ...]
    version: tuple[int, int, int]
    source: str


_SYSTEM_COMPOSE = ("docker", "compose")


def _compose_short_version(runner: Runner, invocation: tuple[str, ...]):
    result = _run(runner, [*invocation, "version", "--short"])
    if result.returncode != 0:
        return None
    return _parse_compose_version(result.stdout)


def resolve_compose_runtime(
    host: HostInfo,
    runner: Runner,
    *,
    allow_download: bool = True,
    downloader: "Downloader | None" = None,
    cache_root: Path | None = None,
) -> ComposeRuntime:
    system_version = _compose_short_version(runner, _SYSTEM_COMPOSE)
    if system_version is not None and system_version >= COMPOSE_MINIMUM:
        return ComposeRuntime(_SYSTEM_COMPOSE, system_version, "system")

    path = compose_cache_path(host, cache_root=cache_root)
    if not path.is_file():
        if not allow_download:
            raise DockerError(
                "COMPOSE_UNAVAILABLE",
                "無法使用 Docker Compose。",
                "請安裝 Docker Compose v2.24 以上，或執行 setup 以自動下載自帶版本。",
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        _download_compose(
            compose_download_url(host),
            path,
            compose_expected_sha256(host),
            downloader=downloader or urlopen_download,
        )

    bundled_version = _compose_short_version(runner, (str(path),))
    if bundled_version is None:
        raise DockerError(
            "COMPOSE_BUNDLED_UNUSABLE",
            "自帶 Docker Compose 無法執行。",
            "請刪除 cache 目錄下的 compose 後重試，或安裝系統 Docker Compose v2.24 以上。",
        )
    return ComposeRuntime((str(path),), bundled_version, "bundled")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd scripts && python -m pytest tests/test_docker_launcher.py -k resolve -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/launcher/docker.py scripts/tests/test_docker_launcher.py
git commit -m "feat(launcher): resolve compose runtime, preferring system then bundled"
```

---

### Task 5: Thread `invocation` through `compose_command`, all compose ops, and `preflight`

**Files:**
- Modify: `scripts/launcher/docker.py`
- Test: `scripts/tests/test_docker_launcher.py`

**Interfaces:**
- Consumes: `resolve_compose_runtime`, `ComposeRuntime` (Task 4).
- Produces:
  - `compose_command(project_root, *arguments, env_file=None, override_file=None, invocation=("docker", "compose")) -> list[str]` (new trailing kw-arg; default preserves current contract).
  - `_compose_required`, `validate_compose`, `compose_up`, `compose_down`, `compose_service_states`, `compose_up_services` each gain `invocation: tuple[str, ...] = ("docker", "compose")`.
  - `@dataclass DockerPreflight: docker_version: str; compose: ComposeRuntime` with properties `compose_version` (→ `compose.version`) and `invocation` (→ `compose.invocation`).
  - `preflight(runner, host, *, allow_download=True, downloader=None, cache_root=None) -> DockerPreflight`.

- [ ] **Step 1: Update existing preflight tests + add invocation tests**

In `scripts/tests/test_docker_launcher.py`, replace `test_preflight_requires_running_daemon_and_compose_224` and `test_preflight_returns_actionable_failures` with:

```python
def test_preflight_requires_running_daemon_and_returns_system_runtime():
    runner = FakeRunner((result(stdout="27.0.0\n"), result(stdout="2.24.7\n")))
    report = preflight(runner, LINUX)
    assert report.docker_version == "27.0.0"
    assert report.compose_version == (2, 24, 7)
    assert report.invocation == ("docker", "compose")
    assert [call[0] for call in runner.commands] == [
        ["docker", "version", "--format", "{{.Server.Version}}"],
        ["docker", "compose", "version", "--short"],
    ]


def test_preflight_rejects_unavailable_daemon():
    with pytest.raises(DockerError) as raised:
        preflight(FakeRunner((result(1, stderr="daemon unavailable"),)), LINUX)
    assert raised.value.code == "DOCKER_DAEMON_UNAVAILABLE"
    assert raised.value.hint


def test_compose_command_accepts_bundled_invocation(tmp_path):
    root = tmp_path.resolve()
    command = compose_command(root, "up", "-d", invocation=("/cache/docker-compose",))
    assert command[:1] == ["/cache/docker-compose"]
    assert command[1:3] == ["--env-file", str(root / ".env")]
    assert command[-2:] == ["up", "-d"]


def test_compose_up_uses_supplied_invocation(tmp_path):
    runner = FakeRunner((result(),))
    compose_up(tmp_path, runner, invocation=("/cache/docker-compose",))
    assert runner.commands[0][0][0] == "/cache/docker-compose"
    assert runner.commands[0][0][-4:] == ["up", "-d", "--build", "--remove-orphans"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd scripts && python -m pytest tests/test_docker_launcher.py -k "preflight or invocation or bundled_invocation" -v`
Expected: FAIL (`preflight()` missing `host` arg / `compose_command` has no `invocation`).

- [ ] **Step 3: Implement — update `compose_command`**

In `scripts/launcher/docker.py`, change `compose_command`:

```python
def compose_command(
    project_root: Path,
    *arguments: str,
    env_file: Path | None = None,
    override_file: Path | None = None,
    invocation: tuple[str, ...] = ("docker", "compose"),
) -> list[str]:
    root = Path(project_root).resolve()
    env = Path(env_file).resolve() if env_file is not None else root / ".env"
    override = (
        Path(override_file).resolve()
        if override_file is not None
        else root / ".ai-drawing/compose.local.yaml"
    )
    return [
        *invocation,
        "--env-file",
        str(env),
        "-f",
        str(root / "docker-compose.yml"),
        "-f",
        str(override),
        *arguments,
    ]
```

- [ ] **Step 4: Implement — thread `invocation` through the compose ops**

Update each function signature and its internal `compose_command(...)` call to pass `invocation`:

```python
def _compose_required(
    project_root, runner, *arguments, code, message,
    invocation: tuple[str, ...] = ("docker", "compose"),
):
    root = Path(project_root).resolve()
    result = _run(runner, compose_command(root, *arguments, invocation=invocation), cwd=root)
    if result.returncode != 0:
        raise DockerError(code, message, "請執行 `setup.ps1 status` 或 `setup.sh status` 檢查服務，再查看 logs。")


def validate_compose(project_root, env_file, override_file, runner, invocation=("docker", "compose")) -> bool:
    root = Path(project_root).resolve()
    result = _run(
        runner,
        compose_command(root, "config", "--quiet", env_file=env_file, override_file=override_file, invocation=invocation),
        cwd=root,
    )
    return result.returncode == 0


def compose_up(project_root, runner, invocation=("docker", "compose")) -> None:
    _compose_required(project_root, runner, "up", "-d", "--build", "--remove-orphans",
        code="COMPOSE_UP_FAILED", message="Docker 服務啟動失敗。", invocation=invocation)


def compose_down(project_root, runner, invocation=("docker", "compose")) -> None:
    _compose_required(project_root, runner, "down", "--remove-orphans", "--timeout=10",
        code="COMPOSE_DOWN_FAILED", message="Docker 服務停止失敗。", invocation=invocation)


def compose_service_states(project_root, runner, invocation=("docker", "compose")) -> dict[str, str]:
    root = Path(project_root).resolve()
    result = _run(runner, compose_command(root, "ps", "--all", "--format", "json", invocation=invocation), cwd=root)
    # ... rest of the existing body unchanged ...


def compose_up_services(project_root, runner, services, invocation=("docker", "compose")) -> None:
    if not services:
        return
    _compose_required(project_root, runner, "up", "-d", "--no-deps", *sorted(services),
        code="COMPOSE_RESTORE_FAILED", message="無法還原先前的 Docker Compose 服務集合。", invocation=invocation)
```

Keep every other line of those function bodies exactly as-is; only the signature and the `compose_command(...)` call within each gain `invocation=invocation`.

- [ ] **Step 5: Implement — update `DockerPreflight` and `preflight`**

Replace the existing `DockerPreflight` dataclass and `preflight` function:

```python
@dataclass(frozen=True)
class DockerPreflight:
    docker_version: str
    compose: ComposeRuntime

    @property
    def compose_version(self) -> tuple[int, int, int]:
        return self.compose.version

    @property
    def invocation(self) -> tuple[str, ...]:
        return self.compose.invocation


def preflight(
    runner: Runner,
    host: HostInfo,
    *,
    allow_download: bool = True,
    downloader: "Downloader | None" = None,
    cache_root: Path | None = None,
) -> DockerPreflight:
    daemon = _run(runner, ["docker", "version", "--format", "{{.Server.Version}}"])
    docker_version = daemon.stdout.strip()
    if daemon.returncode != 0 or not docker_version:
        raise DockerError(
            "DOCKER_DAEMON_UNAVAILABLE",
            "Docker daemon 尚未就緒。",
            "請啟動 Docker Desktop 或 Docker Engine，確認 `docker version` 可用。",
        )
    runtime = resolve_compose_runtime(
        host, runner, allow_download=allow_download, downloader=downloader, cache_root=cache_root
    )
    return DockerPreflight(docker_version=docker_version, compose=runtime)
```

Remove the now-unused inline compose-version/`COMPOSE_UNAVAILABLE`/`COMPOSE_VERSION_UNSUPPORTED` block that was in the old `preflight` (that logic now lives in `resolve_compose_runtime`).

- [ ] **Step 6: Run the full docker test module**

Run: `cd scripts && python -m pytest tests/test_docker_launcher.py -v`
Expected: PASS (all — including the unchanged `test_compose_command_uses_explicit_env_base_and_override`, which still asserts the `("docker","compose")` default).

- [ ] **Step 7: Commit**

```bash
git add scripts/launcher/docker.py scripts/tests/test_docker_launcher.py
git commit -m "feat(launcher): thread compose invocation through ops and preflight"
```

---

### Task 6: Wire the resolved invocation into `DefaultServices` (cli.py)

**Files:**
- Modify: `scripts/launcher/cli.py`
- Test: `scripts/tests/test_cli.py`

**Interfaces:**
- Consumes: `docker.preflight(runner, host, *, allow_download)` returning `DockerPreflight` with `.invocation` (Task 5); `docker.resolve_compose_runtime`.
- Produces: `DefaultServices.preflight(self, *, allow_download=True)` storing `self._compose`; every compose call routes `invocation=self._compose_invocation()`.

- [ ] **Step 1: Update the cli call sites for `allow_download`**

In `scripts/launcher/cli.py`, `_run` (around lines 1806–1821) currently calls `services.preflight()` in two places. Change:
- setup/start/reconfigure branch → `services.preflight(allow_download=True)`
- status/dry-run branch → `services.preflight(allow_download=False)`

- [ ] **Step 2: Update `DefaultServices`**

In `DefaultServices.__init__`, after `self.runner = ...`, add:

```python
        self._compose = None
```

Replace `DefaultServices.preflight`:

```python
    def preflight(self, *, allow_download: bool = True) -> None:
        self._compose = docker.preflight(
            self.runner, self.host, allow_download=allow_download
        )
```

Add a helper (place it just below `preflight`):

```python
    def _compose_invocation(self) -> tuple[str, ...]:
        if self._compose is None:
            # Commands that skip preflight (stop/logs) still need a usable compose;
            # reuse a cached bundled binary if present, but never download here.
            try:
                self._compose = docker.resolve_compose_runtime(
                    self.host, self.runner, allow_download=False
                )
            except docker.DockerError:
                return ("docker", "compose")
        return self._compose.invocation
```

Then pass `invocation=self._compose_invocation()` in every `DefaultServices` compose call:
- `write_configuration` → `docker.validate_compose(..., self.runner, invocation=self._compose_invocation())` (inside the `validate=lambda env, override: ...`)
- `validate_current_compose` → `docker.validate_compose(..., self.runner, invocation=self._compose_invocation())`
- `compose_running_services` → `docker.compose_service_states(self.project_root, self.runner, invocation=self._compose_invocation())`
- `compose_up_services` → `docker.compose_up_services(self.project_root, self.runner, services, invocation=self._compose_invocation())`
- `compose_up` → `docker.compose_up(self.project_root, self.runner, invocation=self._compose_invocation())`
- `compose_down` → `docker.compose_down(self.project_root, self.runner, invocation=self._compose_invocation())`
- `status` → `docker.compose_service_states(self.project_root, self.runner, invocation=self._compose_invocation())`
- `compose_logs` → `self.runner.run(docker.compose_command(self.project_root, "logs", "--tail", "200", invocation=self._compose_invocation()), cwd=self.project_root)`

- [ ] **Step 3: Fix the test fake's `preflight` signature**

In `scripts/tests/test_cli.py` line ~90, the fake services define `def preflight(self):`. Update to accept the kwarg:

```python
    def preflight(self, *, allow_download=True):
        self.events.append("preflight")
        if self.preflight_error is not None:
            raise self.preflight_error
```

- [ ] **Step 4: Run the cli test module**

Run: `cd scripts && python -m pytest tests/test_cli.py -v`
Expected: PASS (the fake service overrides all compose methods, so `_compose_invocation` is not exercised there; the signature fix is what keeps `preflight` calls valid).

- [ ] **Step 5: Commit**

```bash
git add scripts/launcher/cli.py scripts/tests/test_cli.py
git commit -m "feat(launcher): use resolved compose invocation for all compose calls"
```

---

### Task 7: Full suite, docs, and PROGRESS update

**Files:**
- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: Run the entire launcher test suite**

Run: `cd scripts && python -m pytest tests/ -q`
Expected: PASS with no failures. If `test_compose_contract.py` (YAML/Dockerfile structure) or any other module fails, fix the regression before continuing — the contract file should be unaffected by these changes.

- [ ] **Step 2: Manual smoke of the resolver decision (optional but recommended)**

On a machine with a modern Docker Compose:

```bash
cd scripts && python -c "from launcher import docker; from launcher.platforms import detect_host; from launcher.runner import SubprocessRunner; rt = docker.resolve_compose_runtime(detect_host(), SubprocessRunner()); print(rt.source, rt.version, rt.invocation)"
```
Expected: `system (2, XX, Y) ('docker', 'compose')` — confirms modern systems take the zero-download path.

- [ ] **Step 3: Update PROGRESS.md**

Edit the `2026-07-24 自帶 Compose fallback（設計）` bullet in `docs/PROGRESS.md`: change its status line from `**狀態：設計已核可，待寫實作計畫與實作。**` to:

```
  **狀態：已實作。** 系統 compose ≥ 2.24 直接沿用；否則下載釘死版 2.32.4 到私有 cache
  （SHA256 校驗、絕不碰 PATH 與 ~/.docker）。status/dry-run 不觸發下載。
```

- [ ] **Step 4: Commit**

```bash
git add docs/PROGRESS.md
git commit -m "docs: record bundled compose fallback implementation"
```

---

## Self-Review Notes

- **Spec coverage:** version pin + checksums (Task 1); asset/arch/cache mapping incl. `COMPOSE_BUNDLED_UNSUPPORTED_ARCH` (Task 2); download+verify with `COMPOSE_DOWNLOAD_FAILED`/`COMPOSE_CHECKSUM_MISMATCH` (Task 3); resolver decision incl. system-preferred, cached-no-download, read-only-no-download, v1/missing fallback, `COMPOSE_BUNDLED_UNUSABLE`, `COMPOSE_UNAVAILABLE` (Task 4); invocation threading + `preflight` (Task 5); cli wiring incl. `allow_download` per command and stop/logs best-effort (Task 6); full suite + docs (Task 7). All spec sections mapped.
- **Privacy guarantee:** cache-only path, absolute-path invocation, no PATH/`~/.docker` writes — enforced by `compose_cache_path` and `_compose_invocation`; no code writes cli-plugins or PATH.
- **Type consistency:** `ComposeRuntime(invocation, version, source)`, `resolve_compose_runtime(host, runner, *, allow_download, downloader, cache_root)`, `preflight(runner, host, *, allow_download, downloader, cache_root)`, `compose_command(..., invocation=...)` — names/signatures identical across Tasks 4–6.
- **Checksum integrity:** real values fetched in Task 1 Step 1; unit tests never depend on them (they inject fake payloads + digests), so tests stay hermetic.
