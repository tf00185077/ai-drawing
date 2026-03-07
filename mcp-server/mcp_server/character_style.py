"""
角色與風格語意對應

將自然語言描述（角色名、風格名）對應至 Stable Diffusion prompt 與 LoRA 參數。
供 AI 解讀「產生 XX 角色、YY 風格」時轉換成可執行的生圖參數。
"""
from dataclasses import dataclass
from typing import Protocol


@dataclass
class ResolveResult:
    """語意解析結果"""

    prompt_part: str  # 要加入 prompt 的關鍵字
    lora: str | None = None  # 若對應到 LoRA，則為路徑或檔名


class CharacterStyleResolver(Protocol):
    """語意對應介面，可替換實作（如從設定檔、API 載入）"""

    def resolve_character(self, name: str) -> ResolveResult | None:
        """依角色名解析，回傳 None 表示未定義"""
        ...

    def resolve_style(self, name: str) -> ResolveResult | None:
        """依風格名解析，回傳 None 表示未定義"""
        ...

    def list_characters(self) -> list[str]:
        """列出所有已定義的角色別名"""
        ...

    def list_styles(self) -> list[str]:
        """列出所有已定義的風格別名"""
        ...


class DefaultCharacterStyleResolver:
    """
    預設語意對應實作

    角色／風格以別名對應至 prompt 關鍵字，便於擴充。
    未來可改為從 JSON/YAML 或 Backend API 載入。
    """

    def __init__(self) -> None:
        # 角色別名 -> prompt 關鍵字（trigger word 等）
        self._characters: dict[str, str] = {
            "初音": "hatsune miku, teal hair, twin tails",
            "雷姆": "rem (re:zero), blue hair",
            "艾米莉亞": "emilia (re:zero), silver hair",
            "sks": "sks person",
            "吉卜力": "ghibli style, studio ghibli",
        }
        # 風格別名 -> (prompt 關鍵字, lora 路徑或 None)
        self._styles: dict[str, tuple[str, str | None]] = {
            "動漫": ("anime style, high quality", None),
            "寫實": ("photorealistic, realistic", None),
            "水彩": ("watercolor painting", None),
            "賽璐珞": ("cel shading, anime", None),
            "油畫": ("oil painting style", None),
        }

    def resolve_character(self, name: str) -> ResolveResult | None:
        key = name.strip()
        key_lower = key.lower()
        for alias, prompt in self._characters.items():
            if alias.lower() == key_lower or alias == key:
                return ResolveResult(prompt_part=prompt)
        return None

    def resolve_style(self, name: str) -> ResolveResult | None:
        key = name.strip()
        key_lower = key.lower()
        for alias, (prompt, lora) in self._styles.items():
            if alias.lower() == key_lower or alias == key:
                return ResolveResult(prompt_part=prompt, lora=lora)
        return None

    def list_characters(self) -> list[str]:
        return list(self._characters.keys())

    def list_styles(self) -> list[str]:
        return list(self._styles.keys())


_default_resolver: CharacterStyleResolver | None = None


def get_resolver() -> CharacterStyleResolver:
    """取得 Resolver 實例（可於測試時替換）"""
    global _default_resolver
    if _default_resolver is None:
        _default_resolver = DefaultCharacterStyleResolver()
    return _default_resolver


def resolve_to_prompt(
    character: str | None = None,
    style: str | None = None,
    base_prompt: str = "1girl, solo",
) -> tuple[str, str | None]:
    """
    將角色、風格解析為完整 prompt 與可選 LoRA。

    Returns:
        (prompt, lora_path | None)
    """
    resolver = get_resolver()
    parts: list[str] = []
    lora: str | None = None

    if character:
        r = resolver.resolve_character(character)
        if r:
            parts.append(r.prompt_part)
            if r.lora:
                lora = r.lora
        else:
            parts.append(character)

    if style:
        r = resolver.resolve_style(style)
        if r:
            parts.append(r.prompt_part)
            if r.lora and not lora:
                lora = r.lora
        else:
            parts.append(style)

    if not parts:
        return (base_prompt, None)

    prompt = f"{base_prompt}, {', '.join(parts)}"
    return (prompt, lora)
