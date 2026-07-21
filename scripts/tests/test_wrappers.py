import os
import shutil
import subprocess

import pytest


def test_wrappers_pin_uv_and_forward_arguments(project_root):
    ps1 = (project_root / "setup.ps1").read_text(encoding="utf-8")
    sh = (project_root / "setup.sh").read_text(encoding="utf-8")
    for content in (ps1, sh):
        assert "0.11.29" in content
        assert "UV_UNMANAGED_INSTALL" in content
        assert "scripts/bootstrap.py" in content
        assert "UV_NO_MODIFY_PATH" in content
        assert "--python 3.12 --no-project" in content
        assert "AI_DRAWING_UV_BIN" in content
    assert "$args" in ps1
    assert '"$@"' in sh


def test_posix_uv_unmanaged_install_and_binary_share_direct_root(project_root):
    sh = (project_root / "setup.sh").read_text(encoding="utf-8")

    assert 'UV_BIN="$UV_UNMANAGED_INSTALL/uv"' in sh
    assert 'UV_BIN="$UV_UNMANAGED_INSTALL/bin/uv"' not in sh


@pytest.mark.skipif(os.name == "nt", reason="POSIX fake-installer execution")
def test_posix_cold_cache_uses_offline_fake_installer_direct_root(
    tmp_path,
    project_root,
):
    shell = shutil.which("sh")
    assert shell is not None
    project = tmp_path / "project"
    project.mkdir()
    shutil.copy2(project_root / "setup.sh", project / "setup.sh")
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    args_file = tmp_path / "uv-args.txt"
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        """#!/bin/sh
output=''
while [ \"$#\" -gt 0 ]; do
  if [ \"$1\" = '-o' ]; then output=$2; shift 2; else shift; fi
done
cat > \"$output\" <<'INSTALLER'
#!/bin/sh
mkdir -p \"$UV_UNMANAGED_INSTALL\"
cat > \"$UV_UNMANAGED_INSTALL/uv\" <<'UV'
#!/bin/sh
printf '%s\\n' \"$@\" > \"$WRAPPER_ARGS_FILE\"
UV
chmod +x \"$UV_UNMANAGED_INSTALL/uv\"
INSTALLER
""",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        "HOME": str(tmp_path / "home"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "TMPDIR": str(tmp_path),
        "WRAPPER_ARGS_FILE": str(args_file),
    }

    result = subprocess.run(
        [shell, str(project / "setup.sh"), "status"],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    installed = tmp_path / "cache/ai-drawing/uv/0.11.29/uv"
    assert installed.is_file()
    assert args_file.read_text(encoding="utf-8").splitlines() == [
        "run",
        "--python",
        "3.12",
        "--no-project",
        "scripts/bootstrap.py",
        "status",
    ]


def test_posix_wrapper_preflights_safe_downloader_fallback(project_root):
    sh = (project_root / "setup.sh").read_text(encoding="utf-8")

    assert "command -v curl" in sh
    assert "command -v wget" in sh
    assert "BOOTSTRAP_DOWNLOADER_MISSING" in sh
    assert "BOOTSTRAP_DOWNLOAD_FAILED" in sh
    assert "mktemp" in sh
    assert "curl -LsSf" in sh and '-o "$UV_INSTALLER"' in sh
    assert "wget -qO" in sh and '"$UV_INSTALLER"' in sh
    assert "| sh" not in sh


def test_startup_docs_use_copyable_remote_and_describe_cold_cache(project_root):
    expected_clone = "git clone https://github.com/tf00185077/ai-drawing.git"
    readme = (project_root / "README.md").read_text(encoding="utf-8")
    guide = (project_root / "docs/setup-guide.md").read_text(encoding="utf-8")

    for document in (readme, guide):
        assert expected_clone in document
        assert "<repository-url>" not in document
        assert "cold cache" in document
        assert "自動偵測" in document
        assert "--device" in document
    assert "curl 或 wget" in guide
    assert "Backend API / Dashboard" in guide
    assert "CLI `status`" in guide
