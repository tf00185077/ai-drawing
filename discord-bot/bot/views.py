"""Discord UI 元件：兩層 select + 生圖 modal。薄 glue，邏輯委派給 api_client/validation。"""
import asyncio

import discord

from .api_client import BackendError
from .validation import ValidationError, parse_count, parse_dimension, parse_video_contract

MODAL_DEFAULTS_TIMEOUT_SECONDS = 2.0


def build_preset_options(presets: list[dict]) -> list[discord.SelectOption]:
    options = []
    for p in presets[:25]:
        label = p.get("chinese_name") or p.get("name") or p["id"]
        desc = (p.get("name") or "")[:100] or None
        options.append(discord.SelectOption(label=str(label)[:100], value=p["id"], description=desc))
    return options


def build_profile_options(profiles: list[str]) -> list[discord.SelectOption]:
    return [discord.SelectOption(label=str(name)[:100], value=str(name)) for name in profiles[:25]]


class DrawModal(discord.ui.Modal, title="生圖設定"):
    def __init__(self, api, preset_id: str, profile: str | None,
                 positive_default: str, negative_default: str):
        super().__init__()
        self._api = api
        self._preset_id = preset_id
        self._profile = profile
        self.positive_prompt = discord.ui.TextInput(
            label="正向 Prompt（preset 預設，可編輯）",
            style=discord.TextStyle.paragraph,
            default=positive_default,
            required=True,
            max_length=4000,
        )
        self.negative_prompt = discord.ui.TextInput(
            label="負向 Prompt（preset 預設，可編輯）",
            style=discord.TextStyle.paragraph,
            default=negative_default,
            required=False,
            max_length=4000,
        )
        self.width = discord.ui.TextInput(label="寬 (256-2048)", default="1024", required=True, max_length=4)
        self.height = discord.ui.TextInput(label="高 (256-2048)", default="1024", required=True, max_length=4)
        self.count = discord.ui.TextInput(label="張數 (1-8)", default="4", required=False, max_length=1)
        for item in (
            self.positive_prompt,
            self.negative_prompt,
            self.width,
            self.height,
            self.count,
        ):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            width = parse_dimension(self.width.value, field="寬")
            height = parse_dimension(self.height.value, field="高")
            count = parse_count(self.count.value)
        except ValidationError as exc:
            await interaction.response.send_message(f"⚠️ {exc}，請重跑 /draw", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            job_id = await self._api.compose_and_submit(
                self._preset_id,
                self._profile,
                self.positive_prompt.value,
                self.negative_prompt.value,
                width,
                height,
                count,
            )
        except BackendError as exc:
            await interaction.followup.send(f"❌ {exc}", ephemeral=True)
            return
        except Exception:
            await interaction.followup.send("❌ 後端連不上，請確認 backend 有啟動", ephemeral=True)
            return
        await interaction.followup.send(
            f"✅ 已排入生圖（{count} 張）\njob id：`{job_id}`\n用 `/result id:{job_id}` 查詢結果",
            ephemeral=True,
        )


class FixedVideoModal(discord.ui.Modal):
    """Collect the five editable fields after slash-command attachment selection."""

    def __init__(self, api, mode: str, image: discord.Attachment,
                 driver_video: discord.Attachment | None = None):
        if mode not in {"animegen", "wan22_animate"}:
            raise ValueError(f"unsupported fixed-video mode: {mode}")
        if mode == "wan22_animate" and driver_video is None:
            raise ValueError("wan22_animate requires a driver video")
        title = "AnimeGen I2V 設定" if mode == "animegen" else "Wan2.2 Animate 設定"
        super().__init__(title=title)
        self._api = api
        self.mode = mode
        self.image = image
        self.driver_video = driver_video
        self.prompt = discord.ui.TextInput(
            label="動作 Prompt",
            style=discord.TextStyle.paragraph,
            placeholder="描述人物動作、幅度、節奏與鏡頭穩定要求",
            required=True,
            max_length=4000,
        )
        self.negative_prompt = discord.ui.TextInput(
            label="負向 Prompt（選填）",
            style=discord.TextStyle.paragraph,
            placeholder="例如 camera shake, face distortion, flicker",
            required=False,
            max_length=4000,
        )
        self.total_seconds = discord.ui.TextInput(
            label="總秒數／首末幀跨度 (1-20)",
            default="3",
            required=True,
            max_length=5,
        )
        self.source_frames = discord.ui.TextInput(
            label="原始總幀數 (17-321，須為 4n+1)",
            default="49",
            required=True,
            max_length=3,
        )
        self.film_target_frames = discord.ui.TextInput(
            label="FILM 最終總幀數 (17-1921)",
            default="97",
            required=True,
            max_length=4,
        )
        for item in (
            self.prompt,
            self.negative_prompt,
            self.total_seconds,
            self.source_frames,
            self.film_target_frames,
        ):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        prompt = self.prompt.value.strip()
        try:
            if not prompt:
                raise ValidationError("動作 Prompt 不可空白")
            seconds, source, target = parse_video_contract(
                self.total_seconds.value,
                self.source_frames.value,
                self.film_target_frames.value,
            )
        except ValidationError as exc:
            command = "/animegen_i2v" if self.mode == "animegen" else "/wan22_animate"
            await interaction.response.send_message(
                f"⚠️ {exc}，請重跑 {command}", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            image_data = await self.image.read()
            negative = self.negative_prompt.value.strip() or None
            if self.mode == "animegen":
                job_id = await self._api.submit_animegen_i2v(
                    image=(self.image.filename, image_data, self.image.content_type or ""),
                    prompt=prompt,
                    negative_prompt=negative,
                    total_seconds=seconds,
                    source_frames=source,
                    film_target_frames=target,
                )
                label = "AnimeGen I2V"
            else:
                assert self.driver_video is not None
                driver_data = await self.driver_video.read()
                job_id = await self._api.submit_wan22_animate(
                    reference_image=(
                        self.image.filename,
                        image_data,
                        self.image.content_type or "",
                    ),
                    driver_video=(
                        self.driver_video.filename,
                        driver_data,
                        self.driver_video.content_type or "",
                    ),
                    prompt=prompt,
                    negative_prompt=negative,
                    total_seconds=seconds,
                    source_frames=source,
                    film_target_frames=target,
                )
                label = "Wan2.2 Animate 動作轉移"
        except BackendError as exc:
            await interaction.followup.send(f"❌ 後端拒絕：{exc}", ephemeral=True)
            return
        except Exception:
            await interaction.followup.send(
                "❌ 後端連不上或附件讀取失敗", ephemeral=True
            )
            return

        await interaction.followup.send(
            f"✅ {label} 已排入佇列\njob id：`{job_id}`\n"
            f"用 `/result id:{job_id}` 查詢結果",
            ephemeral=True,
        )


async def send_draw_modal(interaction: discord.Interaction, api, preset_id: str,
                          profile: str | None) -> None:
    try:
        positive_default, negative_default = await asyncio.wait_for(
            api.get_prompt_defaults(preset_id, profile),
            timeout=MODAL_DEFAULTS_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        await interaction.response.send_message(
            "❌ 讀取 preset Prompt 逾時，請重試；Backend 可能暫時忙碌",
            ephemeral=True,
        )
        return
    except BackendError as exc:
        await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
        return
    except Exception:
        await interaction.response.send_message(
            "❌ 後端連不上，請確認 backend 有啟動", ephemeral=True
        )
        return

    if len(positive_default) > 4000 or len(negative_default) > 4000:
        await interaction.response.send_message(
            "❌ 此 preset 的 Prompt 超過 Discord 4000 字限制，無法安全顯示",
            ephemeral=True,
        )
        return

    await interaction.response.send_modal(
        DrawModal(
            api,
            preset_id,
            profile,
            positive_default,
            negative_default,
        )
    )


class ProfileSelect(discord.ui.Select):
    def __init__(self, api, preset_id: str, profiles: list[str]):
        super().__init__(placeholder="選擇風格變體（profile）", options=build_profile_options(profiles))
        self._api = api
        self._preset_id = preset_id

    async def callback(self, interaction: discord.Interaction):
        await send_draw_modal(
            interaction, self._api, self._preset_id, self.values[0]
        )


class PresetSelect(discord.ui.Select):
    def __init__(self, api, presets: list[dict]):
        super().__init__(placeholder="選擇畫風 preset", options=build_preset_options(presets))
        self._api = api
        self._presets = {p["id"]: p for p in presets}

    async def callback(self, interaction: discord.Interaction):
        preset = self._presets[self.values[0]]
        profiles = preset.get("profiles") or []
        if profiles:
            view = discord.ui.View(timeout=300)
            view.add_item(ProfileSelect(self._api, preset["id"], profiles))
            await interaction.response.edit_message(content="選擇風格變體：", view=view)
        else:
            await send_draw_modal(interaction, self._api, preset["id"], None)


class PresetView(discord.ui.View):
    def __init__(self, api, presets: list[dict]):
        super().__init__(timeout=300)
        self.add_item(PresetSelect(api, presets))
