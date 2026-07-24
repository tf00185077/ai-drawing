from bot.views import DrawModal, build_preset_options, build_profile_options


def test_preset_options_prefers_chinese_name():
    opts = build_preset_options([
        {"id": "a", "name": "Alpha", "chinese_name": "阿爾法", "profiles": []},
        {"id": "b", "name": "Beta", "profiles": []},
    ])
    assert [(o.label, o.value) for o in opts] == [("阿爾法", "a"), ("Beta", "b")]


def test_preset_options_capped_at_25():
    presets = [{"id": str(i), "name": f"n{i}", "profiles": []} for i in range(40)]
    assert len(build_preset_options(presets)) == 25


def test_profile_options():
    opts = build_profile_options(["day", "night"])
    assert [o.value for o in opts] == ["day", "night"]


def test_draw_modal_has_four_inputs():
    modal = DrawModal(api=None, preset_id="p", profile=None)
    labels = [child.label for child in modal.children]
    assert len(labels) == 4
    # prompt / 寬 / 高 / 張數 四欄都在
    assert any("寬" in l for l in labels)
    assert any("高" in l for l in labels)
    assert any("張數" in l for l in labels)
