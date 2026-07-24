"""Discord UI 元件：兩層 select + 生圖 modal。薄 glue，邏輯委派給 api_client/validation。"""
import discord

from .api_client import BackendError
from .validation import ValidationError, parse_count, parse_dimension


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
    def __init__(self, api, preset_id: str, profile: str | None):
        super().__init__()
        self._api = api
        self._preset_id = preset_id
        self._profile = profile
        self.prompt = discord.ui.TextInput(
            label="Prompt", style=discord.TextStyle.paragraph, required=True, max_length=2000
        )
        self.width = discord.ui.TextInput(label="寬 (256-2048)", default="1024", required=True, max_length=4)
        self.height = discord.ui.TextInput(label="高 (256-2048)", default="1024", required=True, max_length=4)
        self.count = discord.ui.TextInput(label="張數 (1-8)", default="4", required=False, max_length=1)
        for item in (self.prompt, self.width, self.height, self.count):
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
                self._preset_id, self._profile, self.prompt.value, width, height, count
            )
        except BackendError as exc:
            await interaction.followup.send(f"❌ {exc}", ephemeral=True)
            return
        await interaction.followup.send(
            f"✅ 已排入生圖（{count} 張）\njob id：`{job_id}`\n用 `/result id:{job_id}` 查詢結果",
            ephemeral=True,
        )


class ProfileSelect(discord.ui.Select):
    def __init__(self, api, preset_id: str, profiles: list[str]):
        super().__init__(placeholder="選擇風格變體（profile）", options=build_profile_options(profiles))
        self._api = api
        self._preset_id = preset_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(DrawModal(self._api, self._preset_id, self.values[0]))


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
            await interaction.response.send_modal(DrawModal(self._api, preset["id"], None))


class PresetView(discord.ui.View):
    def __init__(self, api, presets: list[dict]):
        super().__init__(timeout=300)
        self.add_item(PresetSelect(api, presets))
