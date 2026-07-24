import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import bot.views as views
from bot.views import (
    DrawModal,
    build_preset_options,
    build_profile_options,
    send_draw_modal,
)


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


def test_draw_modal_prefills_composed_positive_and_negative_prompts():
    modal = DrawModal(
        api=None,
        preset_id="p",
        profile=None,
        positive_default="preset positive",
        negative_default="preset negative",
    )
    labels = [child.label for child in modal.children]
    assert len(labels) == 5
    assert any("正向 Prompt" in label for label in labels)
    assert any("負向 Prompt" in label for label in labels)
    assert modal.positive_prompt.default == "preset positive"
    assert modal.negative_prompt.default == "preset negative"
    assert any("寬" in label for label in labels)
    assert any("高" in label for label in labels)
    assert any("張數" in label for label in labels)


async def test_send_draw_modal_fails_before_discord_hook_timeout(monkeypatch):
    class SlowApi:
        async def get_prompt_defaults(self, preset_id, profile):
            await asyncio.sleep(0.05)
            return "positive", "negative"

    monkeypatch.setattr(
        views, "MODAL_DEFAULTS_TIMEOUT_SECONDS", 0.01, raising=False
    )
    response = SimpleNamespace(
        send_message=AsyncMock(),
        send_modal=AsyncMock(),
    )
    interaction = SimpleNamespace(response=response)

    await send_draw_modal(interaction, SlowApi(), "preset", "profile")

    response.send_modal.assert_not_awaited()
    response.send_message.assert_awaited_once()
    assert "逾時" in response.send_message.await_args.args[0]
