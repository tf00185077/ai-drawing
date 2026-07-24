"""Bot 進入點：註冊 /draw、/result 到指定 guild。"""
import io
import re

import discord
from discord import app_commands

from .api_client import ApiClient, BackendError
from .config import Config, load_config
from .views import PresetView

DISCORD_UPLOAD_LIMIT_BYTES = 24 * 1024 * 1024
DISCORD_MESSAGE_LIMIT = 2000
MAX_FAILED_MEMBER_DETAILS = 4
MAX_FAILURE_REASON_CHARS = 160
JOB_ID_PATTERN = re.compile(
    r"(?<![0-9a-fA-F])[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?![0-9a-fA-F])"
)


def normalize_job_id(value: str) -> str | None:
    """Extract one UUID from plain IDs or copied Discord command text."""
    matches = JOB_ID_PATTERN.findall(value)
    if len(matches) != 1:
        return None
    return matches[0].lower()


def _mixed_batch_warning(outcome: dict) -> str | None:
    failed = (
        outcome.get("batch_failed")
        if type(outcome.get("batch_failed")) is int
        else 0
    )
    if failed <= 0:
        return None
    total = (
        outcome.get("batch_total")
        if type(outcome.get("batch_total")) is int
        else 0
    )
    completed = (
        outcome.get("batch_completed")
        if type(outcome.get("batch_completed")) is int
        else 0
    )
    raw_members = outcome.get("failed_members")
    members = (
        [item for item in raw_members if isinstance(item, dict)]
        if isinstance(raw_members, list)
        else []
    )
    members = sorted(
        enumerate(members),
        key=lambda pair: (
            pair[1].get("batch_index")
            if type(pair[1].get("batch_index")) is int
            else 2**31,
            pair[0],
        ),
    )
    details: list[str] = []
    for _, member in members[:MAX_FAILED_MEMBER_DETAILS]:
        batch_index = member.get("batch_index")
        ordinal = batch_index + 1 if type(batch_index) is int else "?"
        raw_reason = member.get("message") or member.get("code")
        reason = (
            raw_reason if isinstance(raw_reason, str) else "未知錯誤"
        )[:MAX_FAILURE_REASON_CHARS]
        details.append(f"第 {ordinal} 張：{reason}")
    omitted = max(failed - len(details), len(members) - len(details), 0)
    if omitted:
        details.append(f"其餘 {omitted} 張失敗已省略")
    suffix = f"（{'；'.join(details)}）" if details else ""
    warning = (
        f"⚠️ 本輪已完成：成功 {completed}/{total}；"
        f"失敗 {failed}/{total}{suffix}"
    )
    return warning[:DISCORD_MESSAGE_LIMIT]


def build_bot(config: Config):
    intents = discord.Intents.none()
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)
    api = ApiClient(config.backend_base_url)
    guild = discord.Object(id=config.guild_id)

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

    @tree.command(name="result", description="用 job id 反查生圖結果", guild=guild)
    @app_commands.describe(id="生圖時取得的 job id")
    async def result(interaction: discord.Interaction, id: str):
        await interaction.response.defer(thinking=True)
        job_id = normalize_job_id(id)
        if job_id is None:
            await interaction.followup.send(
                "❌ job id 格式錯誤；請貼上訊息中的 UUID，或整段 `/result id:...`"
            )
            return
        try:
            outcome = await api.collect_job_result(job_id)
        except BackendError as exc:
            if exc.status_code == 404:
                await interaction.followup.send("找不到這個 job id")
            else:
                await interaction.followup.send(f"❌ 後端錯誤：{exc}")
            return
        except Exception:
            await interaction.followup.send("❌ 後端連不上，請確認 backend 有啟動")
            return

        status = outcome["status"]
        if status in ("queued", "running"):
            await interaction.followup.send(f"⏳ 狀態：{status}，尚未完成")
            return
        if status == "failed":
            batch_detail = _mixed_batch_warning(outcome)
            if batch_detail:
                batch_detail = batch_detail.removeprefix("⚠️ 本輪已完成：")
                detail = batch_detail
            else:
                raw_node_errors = outcome.get("node_errors")
                node_reasons = []
                if isinstance(raw_node_errors, list):
                    for item in raw_node_errors[:MAX_FAILED_MEMBER_DETAILS]:
                        raw_reason = (
                            item.get("reason")
                            if isinstance(item, dict)
                            else item
                        )
                        if isinstance(raw_reason, str):
                            node_reasons.append(
                                raw_reason[:MAX_FAILURE_REASON_CHARS]
                            )
                errs = "；".join(node_reasons)
                detail = (
                    errs
                    or outcome.get("error")
                    or "未知錯誤"
                )
            await interaction.followup.send(f"❌ 生圖失敗：{detail}")
            return

        images = outcome.get("images") or []
        if not images:
            await interaction.followup.send("完成，但找不到圖檔")
            return

        total = sum(len(data) for _, data in images)
        if total > DISCORD_UPLOAD_LIMIT_BYTES:
            links = "\n".join(outcome.get("urls") or [])
            await interaction.followup.send(f"✅ 完成，共 {len(images)} 張（檔案過大，改附連結）：\n{links}")
        else:
            files = [discord.File(io.BytesIO(data), filename=name) for name, data in images]
            await interaction.followup.send(f"✅ 完成，共 {len(files)} 張", files=files)

        warning = _mixed_batch_warning(outcome)
        if warning:
            await interaction.followup.send(warning)

    @client.event
    async def on_ready():
        await tree.sync(guild=guild)
        print(f"Logged in as {client.user} — commands synced to guild {config.guild_id}")

    return client, tree, api


def main() -> None:
    config = load_config()
    client, _tree, _api = build_bot(config)
    client.run(config.discord_token)


if __name__ == "__main__":
    main()
