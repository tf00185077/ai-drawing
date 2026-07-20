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
