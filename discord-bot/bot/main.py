"""Bot 進入點：註冊 /draw、/result 到指定 guild。"""
from __future__ import annotations

import discord
from discord import app_commands

from .api_client import ApiClient, BackendError
from .config import Config, load_config
from .delivery import DeliveryError, DeliveryLedger, ResultDeliveryService, mixed_batch_warning
from .main_types import normalize_job_id
from .operator_api import OperatorConfig, OperatorDeliveryServer
from .views import FixedVideoModal, PresetView
from .validation import (
    ValidationError,
    parse_video_dimensions,
    validate_discord_attachment,
)

# Backward-compatible private name used by existing tests/callers.
_mixed_batch_warning = mixed_batch_warning

EXECUTION_TARGET_CHOICES = [
    app_commands.Choice(name="Mac（本機）", value="local"),
    app_commands.Choice(name="Windows（Worker）", value="worker"),
]


def _execution_target_value(choice: app_commands.Choice[str] | None) -> str:
    return choice.value if choice is not None else "local"


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
    @app_commands.describe(execution_target="執行位置（預設 Mac 本機）")
    @app_commands.choices(execution_target=EXECUTION_TARGET_CHOICES)
    async def draw(
        interaction: discord.Interaction,
        execution_target: app_commands.Choice[str] | None = None,
    ):
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
            "選擇畫風：",
            view=PresetView(api, presets, _execution_target_value(execution_target)),
            ephemeral=True,
        )

    @tree.command(name="animegen_i2v", description="選圖與輸出尺寸後開啟 AnimeGen I2V 設定", guild=guild)
    @app_commands.describe(
        image="起始圖片；動作與時間選項會在下一步彈窗輸入",
        width="輸出寬度（256–2048，須為 16 的倍數）",
        height="輸出高度（256–2048，須為 16 的倍數）",
        execution_target="執行位置（預設 Mac 本機）",
    )
    @app_commands.choices(execution_target=EXECUTION_TARGET_CHOICES)
    async def animegen_i2v(
        interaction: discord.Interaction,
        image: discord.Attachment,
        width: app_commands.Range[int, 256, 2048],
        height: app_commands.Range[int, 256, 2048],
        execution_target: app_commands.Choice[str] | None = None,
    ):
        try:
            validate_discord_attachment(image, kind="image")
            width, height = parse_video_dimensions(width, height)
        except ValidationError as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
            return
        await interaction.response.send_modal(
            FixedVideoModal(
                api, mode="animegen", image=image, width=width, height=height,
                execution_target=_execution_target_value(execution_target),
            )
        )

    @tree.command(name="wan22_animate", description="選參考圖與driver後開啟互動設定", guild=guild)
    @app_commands.describe(
        reference_image="角色參考圖；其餘選項會在下一步彈窗輸入",
        driver_video="提供臉部與身體動作的driver影片",
        execution_target="執行位置（預設 Mac 本機）",
    )
    @app_commands.choices(execution_target=EXECUTION_TARGET_CHOICES)
    async def wan22_animate(
        interaction: discord.Interaction,
        reference_image: discord.Attachment,
        driver_video: discord.Attachment,
        execution_target: app_commands.Choice[str] | None = None,
    ):
        try:
            validate_discord_attachment(reference_image, kind="image")
            validate_discord_attachment(driver_video, kind="video")
        except ValidationError as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
            return
        await interaction.response.send_modal(
            FixedVideoModal(
                api,
                mode="wan22_animate",
                image=reference_image,
                driver_video=driver_video,
                execution_target=_execution_target_value(execution_target),
            )
        )

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
