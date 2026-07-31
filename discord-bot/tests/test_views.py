import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import bot.views as views
from bot.views import (
    DrawModal,
    FixedVideoModal,
    PresetView,
    ProfileSelect,
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
        execution_target="worker",
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
    assert modal.execution_target == "worker"


async def test_draw_modal_preserves_worker_target_to_backend_submit():
    api = SimpleNamespace(compose_and_submit=AsyncMock(return_value="worker-job"))
    modal = DrawModal(api, "p", "portrait", "positive", "negative", "worker")
    interaction = SimpleNamespace(
        response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )

    await modal.on_submit(interaction)

    assert api.compose_and_submit.await_args.kwargs["execution_target"] == "worker"


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


async def test_draw_selection_chain_preserves_worker_target_into_modal():
    api = SimpleNamespace(get_prompt_defaults=AsyncMock(return_value=("pos", "neg")))
    view = PresetView(
        api, [{"id": "p", "name": "Preset", "profiles": ["portrait"]}], "worker"
    )
    preset_select = view.children[0]
    assert preset_select._execution_target == "worker"

    profile_select = ProfileSelect(api, "p", ["portrait"], "worker")
    assert profile_select._execution_target == "worker"

    response = SimpleNamespace(send_message=AsyncMock(), send_modal=AsyncMock())
    await send_draw_modal(
        SimpleNamespace(response=response), api, "p", "portrait", "worker"
    )
    assert response.send_modal.await_args.args[0].execution_target == "worker"


def test_fixed_video_modal_exposes_all_editable_options_with_short_animation_defaults():
    image = SimpleNamespace(filename="person.png")
    modal = FixedVideoModal(
        api=None, mode="animegen", image=image, width=1024, height=1024
    )

    labels = [child.label for child in modal.children]
    assert len(labels) == 5
    assert any("動作 Prompt" in label for label in labels)
    assert any("負向 Prompt" in label for label in labels)
    assert any("秒數" in label for label in labels)
    assert any("原始總幀數" in label for label in labels)
    assert any("FILM" in label for label in labels)
    assert modal.total_seconds.default == "3"
    assert modal.source_frames.default == "49"
    assert modal.film_target_frames.default == "97"
    assert modal.image is image


async def test_fixed_video_modal_submits_animegen_after_validation():
    api = SimpleNamespace(submit_animegen_i2v=AsyncMock(return_value="video-job"))
    image = SimpleNamespace(
        filename="person.png",
        content_type="image/png",
        read=AsyncMock(return_value=b"png-bytes"),
    )
    modal = FixedVideoModal(
        api=api, mode="animegen", image=image, width=1024, height=1024,
        execution_target="worker",
    )
    modal.prompt._value = "gentle bob and smile"
    modal.negative_prompt._value = "camera shake"
    modal.total_seconds._value = "3"
    modal.source_frames._value = "49"
    modal.film_target_frames._value = "97"
    interaction = SimpleNamespace(
        response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )

    await modal.on_submit(interaction)

    interaction.response.defer.assert_awaited_once_with(ephemeral=True, thinking=True)
    api.submit_animegen_i2v.assert_awaited_once()
    kwargs = api.submit_animegen_i2v.await_args.kwargs
    assert kwargs["prompt"] == "gentle bob and smile"
    assert kwargs["total_seconds"] == 3.0
    assert kwargs["source_frames"] == 49
    assert kwargs["film_target_frames"] == 97
    assert kwargs["width"] == 1024
    assert kwargs["height"] == 1024
    assert kwargs["execution_target"] == "worker"
    assert "video-job" in interaction.followup.send.await_args.args[0]


async def test_fixed_video_modal_submits_wan_reference_and_driver():
    api = SimpleNamespace(submit_wan22_animate=AsyncMock(return_value="wan-job"))
    image = SimpleNamespace(
        filename="reference.webp",
        content_type="image/webp",
        read=AsyncMock(return_value=b"image-bytes"),
    )
    driver = SimpleNamespace(
        filename="driver.mp4",
        content_type="video/mp4",
        read=AsyncMock(return_value=b"video-bytes"),
    )
    modal = FixedVideoModal(
        api=api,
        mode="wan22_animate",
        image=image,
        driver_video=driver,
        execution_target="worker",
    )
    modal.prompt._value = "follow the driver's gentle motion"
    modal.negative_prompt._value = ""
    modal.total_seconds._value = "5"
    modal.source_frames._value = "81"
    modal.film_target_frames._value = "161"
    interaction = SimpleNamespace(
        response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )

    await modal.on_submit(interaction)

    api.submit_wan22_animate.assert_awaited_once()
    kwargs = api.submit_wan22_animate.await_args.kwargs
    assert kwargs["reference_image"] == (
        "reference.webp", b"image-bytes", "image/webp"
    )
    assert kwargs["driver_video"] == ("driver.mp4", b"video-bytes", "video/mp4")
    assert kwargs["negative_prompt"] is None
    assert kwargs["film_target_frames"] == 161
    assert kwargs["execution_target"] == "worker"
    assert "wan-job" in interaction.followup.send.await_args.args[0]


async def test_fixed_video_modal_rejects_invalid_frame_count_before_reading_attachment():
    api = SimpleNamespace(submit_animegen_i2v=AsyncMock())
    image = SimpleNamespace(
        filename="person.png",
        content_type="image/png",
        read=AsyncMock(return_value=b"png-bytes"),
    )
    modal = FixedVideoModal(
        api=api, mode="animegen", image=image, width=1024, height=1024
    )
    modal.prompt._value = "gentle motion"
    modal.total_seconds._value = "3"
    modal.source_frames._value = "50"
    modal.film_target_frames._value = "97"
    interaction = SimpleNamespace(
        response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )

    await modal.on_submit(interaction)

    interaction.response.send_message.assert_awaited_once()
    assert "4n+1" in interaction.response.send_message.await_args.args[0]
    interaction.response.defer.assert_not_awaited()
    image.read.assert_not_awaited()
    api.submit_animegen_i2v.assert_not_awaited()
