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
    assert names == {"draw", "result"}
    assert api._base_url == "http://test"


async def test_result_command_sends_successful_files_before_mixed_warning():
    config = Config(
        discord_token="t",
        guild_id=123,
        backend_base_url="http://test",
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


async def test_result_command_reports_all_failed_batch_members() -> None:
    config = Config(
        discord_token="t",
        guild_id=123,
        backend_base_url="http://test",
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
