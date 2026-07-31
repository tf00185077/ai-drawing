import discord
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.config import Config
from bot.main import _mixed_batch_warning, build_bot, normalize_job_id


def test_normalize_job_id_accepts_discord_copy_forms():
    job_id = "9bbd2e57-5e7e-43db-99e1-06679b6f0e81"
    assert normalize_job_id(job_id) == job_id
    assert normalize_job_id(f"id:{job_id}") == job_id
    assert normalize_job_id(f"`{job_id}`") == job_id
    assert normalize_job_id(f"/result id:{job_id}") == job_id
    assert normalize_job_id(f"  {job_id.upper()}  ") == job_id


def test_normalize_job_id_rejects_missing_or_ambiguous_uuid():
    first = "9bbd2e57-5e7e-43db-99e1-06679b6f0e81"
    second = "11111111-2222-3333-4444-555555555555"
    assert normalize_job_id("not-a-job") is None
    assert normalize_job_id(f"{first} {second}") is None


def test_build_bot_registers_commands():
    config = Config(discord_token="t", guild_id=123, backend_base_url="http://test")
    client, tree, api = build_bot(config)
    guild = discord.Object(id=123)
    names = {c.name for c in tree.get_commands(guild=guild)}
    assert names == {"draw", "animegen_i2v", "wan22_animate", "result"}
    assert api._base_url == "http://test"


async def test_result_command_sends_successful_files_before_mixed_warning(tmp_path):
    config = Config(
        discord_token="t",
        guild_id=123,
        backend_base_url="http://test",
        delivery_ledger_path=tmp_path / "deliveries.json",
    )
    _client, tree, api = build_bot(config)
    guild = discord.Object(id=123)
    result_command = tree.get_command("result", guild=guild)
    job_id = "9bbd2e57-5e7e-43db-99e1-06679b6f0e81"
    api.collect_job_result = AsyncMock(
        return_value={
            "status": "completed",
            "images": [
                ("one.png", b"one"),
                ("two.png", b"two"),
                ("three.png", b"three"),
            ],
            "urls": [],
            "batch_total": 4,
            "batch_completed": 3,
            "batch_failed": 1,
            "failed_members": [
                {
                    "batch_index": 1,
                    "code": "comfyui_execution_error",
                    "message": "ComfyUI execution error",
                }
            ],
        }
    )
    interaction = SimpleNamespace(
        response=SimpleNamespace(defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )

    await result_command.callback(interaction, job_id)

    assert interaction.followup.send.await_count == 2
    success_call, warning_call = interaction.followup.send.await_args_list
    assert "完成，共 3 張" in success_call.args[0]
    assert len(success_call.kwargs["files"]) == 3
    assert "成功 3/4" in warning_call.args[0]
    assert "失敗 1/4" in warning_call.args[0]
    assert "第 2 張" in warning_call.args[0]
    assert "ComfyUI execution error" in warning_call.args[0]


async def test_result_command_explicitly_resends_a_completed_result(tmp_path) -> None:
    config = Config(
        discord_token="t",
        guild_id=123,
        backend_base_url="http://test",
        delivery_ledger_path=tmp_path / "deliveries.json",
    )
    _client, tree, api = build_bot(config)
    result_command = tree.get_command("result", guild=discord.Object(id=123))
    job_id = "9bbd2e57-5e7e-43db-99e1-06679b6f0e81"
    api.collect_job_result = AsyncMock(
        return_value={"status": "completed", "images": [("one.png", b"one")]}
    )
    interaction = SimpleNamespace(
        guild_id=123,
        channel_id=456,
        response=SimpleNamespace(defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )

    await result_command.callback(interaction, job_id)
    await result_command.callback(interaction, job_id)

    assert api.collect_job_result.await_count == 2
    assert interaction.followup.send.await_count == 2
    assert all("files" in call.kwargs for call in interaction.followup.send.await_args_list)


async def test_result_command_reports_all_failed_batch_members(tmp_path) -> None:
    config = Config(
        discord_token="t",
        guild_id=123,
        backend_base_url="http://test",
        delivery_ledger_path=tmp_path / "deliveries.json",
    )
    _client, tree, api = build_bot(config)
    guild = discord.Object(id=123)
    result_command = tree.get_command("result", guild=guild)
    job_id = "9bbd2e57-5e7e-43db-99e1-06679b6f0e81"
    api.collect_job_result = AsyncMock(
        return_value={
            "status": "failed",
            "batch_total": 2,
            "batch_completed": 0,
            "batch_failed": 2,
            "error": "all independent batch members failed",
            "node_errors": [
                {
                    "reason": "RAW-NODE-ERROR-SHOULD-NOT-WIN",
                }
            ],
            "failed_members": [
                {
                    "batch_index": 0,
                    "code": "backend_restarted",
                    "message": "Backend restarted before completion",
                },
                {
                    "batch_index": 1,
                    "code": "comfyui_execution_error",
                    "message": "ComfyUI execution error",
                },
            ],
        }
    )
    interaction = SimpleNamespace(
        response=SimpleNamespace(defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )

    await result_command.callback(interaction, job_id)

    interaction.followup.send.assert_awaited_once()
    message = interaction.followup.send.await_args.args[0]
    assert "生圖失敗" in message
    assert "成功 0/2" in message
    assert "失敗 2/2" in message
    assert "第 1 張" in message
    assert "第 2 張" in message
    assert "RAW-NODE-ERROR-SHOULD-NOT-WIN" not in message


def test_mixed_batch_warning_is_bounded_deterministic_and_aggregated() -> None:
    outcome = {
        "batch_total": 4,
        "batch_completed": 0,
        "batch_failed": 4,
        "failed_members": [
            {
                "batch_index": index,
                "code": "comfyui_execution_error",
                "message": f"member {index} " + ("very long reason " * 100),
            }
            for index in reversed(range(4))
        ],
    }

    first = _mixed_batch_warning(outcome)
    second = _mixed_batch_warning(outcome)

    assert first == second
    assert first is not None
    assert len(first) <= 2000
    assert "成功 0/4" in first
    assert "失敗 4/4" in first
    assert "第 1 張" in first
    assert "第 4 張" in first


async def test_animegen_command_defers_before_download_and_submits_validated_attachment(tmp_path):
    config = Config(discord_token="t", guild_id=123, backend_base_url="http://test",
                    delivery_ledger_path=tmp_path / "deliveries.json")
    _client, tree, api = build_bot(config)
    command = tree.get_command("animegen_i2v", guild=discord.Object(id=123))
    events = []
    response = SimpleNamespace(defer=AsyncMock(side_effect=lambda **kwargs: events.append("defer")))
    attachment = SimpleNamespace(filename="person.png", content_type="image/png", size=12,
        read=AsyncMock(side_effect=lambda: events.append("read") or b"png-bytes"))
    api.submit_animegen_i2v = AsyncMock(return_value="video-job")
    interaction = SimpleNamespace(response=response, followup=SimpleNamespace(send=AsyncMock()))

    await command.callback(interaction, attachment, "wave", 5.0, 81, 321, None)

    assert events == ["defer", "read"]
    response.defer.assert_awaited_once_with(thinking=True, ephemeral=True)
    api.submit_animegen_i2v.assert_awaited_once()
    assert api.submit_animegen_i2v.await_args.kwargs["film_target_frames"] == 321
    assert "video-job" in interaction.followup.send.await_args.args[0]


async def test_wan_command_rejects_oversize_driver_without_reading_it(tmp_path):
    config = Config(discord_token="t", guild_id=123, backend_base_url="http://test",
                    delivery_ledger_path=tmp_path / "deliveries.json")
    _client, tree, api = build_bot(config)
    command = tree.get_command("wan22_animate", guild=discord.Object(id=123))
    reference = SimpleNamespace(filename="ref.png", content_type="image/png", size=10, read=AsyncMock())
    driver = SimpleNamespace(filename="driver.mp4", content_type="video/mp4",
                             size=100 * 1024 * 1024 + 1, read=AsyncMock())
    api.submit_wan22_animate = AsyncMock()
    interaction = SimpleNamespace(response=SimpleNamespace(defer=AsyncMock()),
                                  followup=SimpleNamespace(send=AsyncMock()))

    await command.callback(interaction, reference, driver, "move", 5.0, 81, 321, None)

    interaction.response.defer.assert_awaited_once()
    reference.read.assert_not_awaited()
    driver.read.assert_not_awaited()
    api.submit_wan22_animate.assert_not_awaited()
    assert "大小" in interaction.followup.send.await_args.args[0]
