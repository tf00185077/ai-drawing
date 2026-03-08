"""
描述解析器：從使用者自然語言描述解析出生圖意圖

將「穿和服的初音、動漫風格、1024 解析度」解析為：
- character, style, extra_prompt
- template 選擇（default / default_lora）
- width, height 等參數
"""
from dataclasses import dataclass
import re

from mcp_server.character_style import get_resolver


@dataclass
class ParseResult:
    """解析結果"""

    character: str | None = None
    style: str | None = None
    extra_prompt: str = ""
    template: str = "default"
    width: int | None = None
    height: int | None = None
    raw_prompt: str = ""


# 關鍵字 → 模板
TEMPLATE_HINTS: dict[str, str] = {
    "lora": "default_lora",
    "lora模型": "default_lora",
    "用lora": "default_lora",
}

# 額外描述中的中文 → SD 常用英文（可擴充）
EXTRA_PROMPT_MAP: dict[str, str] = {
    "和服": "kimono",
    "櫻花": "cherry blossom",
    "海邊": "beach",
    "夜景": "night",
}

# 關鍵字 → 解析度
RESOLUTION_HINTS: list[tuple[list[str], tuple[int, int]]] = [
    (["1024", "高解析", "高清", "sdxl"], (1024, 1024)),
    (["512", "低解析"], (512, 512)),
    (["768"], (768, 768)),
]


def _extract_from_list(text: str, candidates: list[str]) -> str | None:
    """從文字中找出第一個匹配的候選"""
    text_lower = text.lower()
    for c in candidates:
        if c.lower() in text_lower:
            return c
    return None


def parse_description(description: str) -> ParseResult:
    """
    解析使用者描述，回傳結構化意圖。

    範例：
        "穿和服的初音，動漫風格，1024" → character=初音, style=動漫, extra=kimono, width=1024
    """
    desc = description.strip()
    if not desc:
        return ParseResult(raw_prompt="1girl, solo")

    resolver = get_resolver()
    chars = resolver.list_characters()
    styles = resolver.list_styles()

    character = _extract_from_list(desc, chars)
    style = _extract_from_list(desc, styles)

    # 選擇模板
    template = "default"
    desc_lower = desc.lower().replace(" ", "")
    for keyword, tpl in TEMPLATE_HINTS.items():
        if keyword in desc_lower or keyword.replace(" ", "") in desc_lower:
            template = tpl
            break
    r = resolver.resolve_style(style) if style else None
    if r and r.lora:
        template = "default_lora"

    # 解析度
    width, height = None, None
    for keywords, (w, h) in RESOLUTION_HINTS:
        for kw in keywords:
            if kw in desc:
                width, height = w, h
                break
        if width is not None:
            break

    # 額外 prompt：移除已辨識的角色/風格/解析度關鍵字，剩餘當作額外描述
    extra_parts: list[str] = []
    remaining = desc
    for c in [character, style] if character or style else []:
        if c:
            remaining = remaining.replace(c, "").strip(" ,，、")
    # 移除常見 filler
    for filler in ["風格", "的", "，", "、"]:
        remaining = remaining.replace(filler, " ").strip()
    for keywords, _ in RESOLUTION_HINTS:
        for kw in keywords:
            remaining = re.sub(re.escape(kw), "", remaining, flags=re.IGNORECASE)
    for kw in TEMPLATE_HINTS:
        remaining = re.sub(re.escape(kw), "", remaining, flags=re.IGNORECASE)
    remaining = re.sub(r"[,，、\s]+", " ", remaining).strip()
    if remaining:
        for zh, en in EXTRA_PROMPT_MAP.items():
            if zh in remaining:
                remaining = remaining.replace(zh, en)
        extra_parts.append(remaining)

    extra_prompt = ", ".join(extra_parts) if extra_parts else ""

    return ParseResult(
        character=character,
        style=style,
        extra_prompt=extra_prompt,
        template=template,
        width=width,
        height=height,
        raw_prompt=desc,
    )
