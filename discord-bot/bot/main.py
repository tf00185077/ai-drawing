"""Bot 進入點：註冊 /draw、/result 到指定 guild。"""
from __future__ import annotations

import discord
from discord import app_commands

from .api_client import ApiClient, BackendError
from .config import Config, load_config
from .delivery import DeliveryError, DeliveryLedger, ResultDeliveryService, mixed_batch_warning
from .main_types import normalize_job_id
from .operator_api import OperatorConfig, OperatorDeliveryServer
from .views import PresetView
from .validation import ValidationError, parse_video_contract, validate_discord_attachment

# Backward-compatible private name used by existing tests/callers.
_mixed_batch_warning = mixed_batch_warning


def build_bot(config: Config):
    intents = discord.Intents.none()
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)
    api = ApiClient(config.backend_base_url)
    delivery = ResultDeliveryService(api, DeliveryLedger(config.delivery_ledger_path))
    guild = discord.Object(id=config.guild_id)
    operator_server: OperatorDeliveryServer | None = None
    if config.operator_token and config.operator_destinations:
        operator_server = OperatorDeliveryServer(
            client,
            delivery,
            OperatorConfig(
                token=config.operator_token,
                destinations=dict(config.operator_destinations),
                port=config.operator_port,
            ),
            config.guild_id,
        )

    @tree.command(name="draw", description="從畫風 preset 直接生圖", guild=guild)
    async def draw(interaction: discord.Interaction):
        try:
            presets = await api.list_presets()
        except BackendError as exc:
            await interaction.response.send_message(f"❌ 後端錯誤：{exc}", ephemeral=True)
            return
        except Exception:
            await interaction.response.send_message("❌ 後端連不上，請確認 backend 有啟動", ephemeral=True)
            return
        if not presets:
            await interaction.response.send_message("目前沒有可用的 preset", ephemeral=True)
            return
        await interaction.response.send_message(
            "選擇畫風：", view=PresetView(api, presets), ephemeral=True
        )

    @tree.command(name="animegen_i2v", description="AnimeGen 單圖 I2V，完成後精確 FILM 補幀", guild=guild)
    @app_commands.describe(image="起始圖片", prompt="動作描述（不經 LLM）", total_seconds="首幀到末幀秒數",
                           source_frames="原始生成總幀數（4n+1）", film_target_frames="FILM 後精確總幀數",
                           negative_prompt="可選負面 prompt")
    async def animegen_i2v(
        interaction: discord.Interaction, image: discord.Attachment, prompt: str,
        total_seconds: app_commands.Range[float, 1.0, 20.0],
        source_frames: app_commands.Range[int, 17, 321],
        film_target_frames: app_commands.Range[int, 17, 1921],
        negative_prompt: str | None = None,
    ):
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            validate_discord_attachment(image, kind="image")
            seconds, source, target = parse_video_contract(total_seconds, source_frames, film_target_frames)
            data = await image.read()
            job_id = await api.submit_animegen_i2v(
                image=(image.filename, data, image.content_type or ""), prompt=prompt,
                negative_prompt=negative_prompt, total_seconds=seconds,
                source_frames=source, film_target_frames=target,
            )
            await interaction.followup.send(f"✅ AnimeGen I2V 已排入佇列\njob id: `{job_id}`")
        except ValidationError as exc:
            await interaction.followup.send(f"❌ {exc}")
        except BackendError as exc:
            await interaction.followup.send(f"❌ 後端拒絕：{exc}")
        except Exception:
            await interaction.followup.send("❌ 後端連不上或附件讀取失敗")

    @tree.command(name="wan22_animate", description="Wan2.2 Animate 參考角色＋driver 動作轉移", guild=guild)
    @app_commands.describe(reference_image="角色 reference 圖", driver_video="提供臉部與身體動作的 driver 影片",
                           prompt="動作轉移描述（不經 LLM）", total_seconds="首幀到末幀秒數",
                           source_frames="原始生成總幀數（4n+1）", film_target_frames="FILM 後精確總幀數",
                           negative_prompt="可選負面 prompt")
    async def wan22_animate(
        interaction: discord.Interaction, reference_image: discord.Attachment,
        driver_video: discord.Attachment, prompt: str,
        total_seconds: app_commands.Range[float, 1.0, 20.0],
        source_frames: app_commands.Range[int, 17, 321],
        film_target_frames: app_commands.Range[int, 17, 1921],
        negative_prompt: str | None = None,
    ):
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            validate_discord_attachment(reference_image, kind="image")
            validate_discord_attachment(driver_video, kind="video")
            seconds, source, target = parse_video_contract(total_seconds, source_frames, film_target_frames)
            reference_data = await reference_image.read()
            driver_data = await driver_video.read()
            job_id = await api.submit_wan22_animate(
                reference_image=(reference_image.filename, reference_data, reference_image.content_type or ""),
                driver_video=(driver_video.filename, driver_data, driver_video.content_type or ""),
                prompt=prompt, negative_prompt=negative_prompt, total_seconds=seconds,
                source_frames=source, film_target_frames=target,
            )
            await interaction.followup.send(f"✅ Wan2.2 Animate 動作轉移已排入佇列\njob id: `{job_id}`")
        except ValidationError as exc:
            await interaction.followup.send(f"❌ {exc}")
        except BackendError as exc:
            await interaction.followup.send(f"❌ 後端拒絕：{exc}")
        except Exception:
            await interaction.followup.send("❌ 後端連不上或附件讀取失敗")

    @tree.command(name="result", description="用 job id 反查生圖或影片結果", guild=guild)
    @app_commands.describe(id="生圖時取得的 job id")
    async def result(interaction: discord.Interaction, id: str):
        await interaction.response.defer(thinking=True)
        job_id = normalize_job_id(id)
        if job_id is None:
            await interaction.followup.send(
                "❌ job id 格式錯誤；請貼上訊息中的 UUID，或整段 `/result id:...`"
            )
            return
        guild_id = getattr(interaction, "guild_id", None) or config.guild_id
        channel_id = getattr(interaction, "channel_id", None) or "unknown"
        try:
            receipt = await delivery.deliver(
                job_id,
                f"interaction:{guild_id}:{channel_id}",
                interaction.followup.send,
                # Invoking /result is itself an explicit request to send the files again.
                # Operator delivery remains deduplicated unless force_resend is requested.
                force_resend=True,
            )
        except DeliveryError as exc:
            prefixes = {
                "job_not_found": "",
                "job_not_completed": "⏳ ",
                "generation_failed": "❌ ",
                "artifacts_missing": "",
            }
            prefix = prefixes.get(exc.code, "❌ ")
            await interaction.followup.send(f"{prefix}{exc}")
            return
        if receipt.deduplicated:
            ids = ", ".join(receipt.message_ids)
            await interaction.followup.send(f"✅ 此結果已送出（Discord message IDs: {ids}）")

    @client.event
    async def on_ready():
        await tree.sync(guild=guild)
        if operator_server is not None:
            await operator_server.start()
        print(f"Logged in as {client.user} — commands synced to guild {config.guild_id}")

    # Expose lifecycle object for controlled shutdown/tests without exposing credentials.
    client.operator_delivery_server = operator_server  # type: ignore[attr-defined]
    return client, tree, api


def main() -> None:
    config = load_config()
    client, _tree, _api = build_bot(config)
    client.run(config.discord_token)


if __name__ == "__main__":
    main()
