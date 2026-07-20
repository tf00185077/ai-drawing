def test_wrappers_pin_uv_and_forward_arguments(project_root):
    ps1 = (project_root / "setup.ps1").read_text(encoding="utf-8")
    sh = (project_root / "setup.sh").read_text(encoding="utf-8")
    for content in (ps1, sh):
        assert "0.11.29" in content
        assert "UV_UNMANAGED_INSTALL" in content
        assert "scripts/bootstrap.py" in content
        assert "UV_NO_MODIFY_PATH" in content
        assert "--python 3.12 --no-project" in content
    assert "$args" in ps1
    assert '"$@"' in sh


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
