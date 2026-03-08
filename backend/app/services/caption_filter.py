"""
WD Tagger 輸出過濾
去除重複、冗餘、雜訊 tag，保留更精簡的 caption 供 LoRA 訓練
"""
import re

# 冗餘規則：當「較具體」tag 存在時，移除「較籠統」tag
# 格式：具體_tag -> [會被移除的籠統_tag]
# 參考 Danbooru implication：具體 implies 籠統，訓練時保留具體即可
REDUNDANCY_RULES: dict[str, list[str]] = {
    # 泳裝
    "one-piece_swimsuit": ["swimsuit"],
    "competition_swimsuit": ["swimsuit"],
    "bikini": ["swimsuit"],
    "swimsuit_under_clothes": ["swimsuit"],
    "blue_one-piece_swimsuit": ["swimsuit", "one-piece_swimsuit"],
    # 坐姿（wariza=正座、seiza=跪坐等 implies sitting）
    "wariza": ["sitting"],
    "seiza": ["sitting"],
    "indian_style": ["sitting"],
    "lotus_position": ["sitting"],
    # 制服
    "serafuku": ["school_uniform"],
    "sailor_collar": ["school_uniform"],
    "grey_sailor_collar": ["school_uniform", "sailor_collar"],
    # 髮型（long_hair 等已足夠，不需額外 hair）
    "long_hair": ["hair"],
    "short_hair": ["hair"],
    "medium_hair": ["hair"],
    "very_long_hair": ["hair", "long_hair"],
    # 瞳色
    "blue_eyes": ["eyes"],
    "red_eyes": ["eyes"],
    "green_eyes": ["eyes"],
    "brown_eyes": ["eyes"],
    "purple_eyes": ["eyes"],
    "grey_eyes": ["eyes"],
    "yellow_eyes": ["eyes"],
    "heterochromia": ["eyes"],
    # 乳量（已標具體時不需 general breasts）
    "large_breasts": ["breasts"],
    "medium_breasts": ["breasts"],
    "small_breasts": ["breasts"],
    "flat_chest": ["breasts"],
    # 服飾細部
    "panties": ["underwear"],
    "bra": ["underwear"],
}

# 雜訊：應直接移除的 tag 模式（正則）或精確匹配
NOISE_PATTERNS: list[tuple[str, bool]] = [
    (r"^;[\w]*$", True),  # ;d 之類的雜訊
    (r"^score_\d+$", True),  # score_9, score_8 等（WD 有時會輸出）
    (r"^\d+$", True),  # 純數字
    (r"^[^a-zA-Z0-9_]+$", True),  # 純符號
]
NOISE_EXACT: set[str] = {";d", ";p", ";)", "()", "1", "0"}

# 最小有效 tag 長度（過短視為雜訊）
MIN_TAG_LEN = 2


def _parse_tags(content: str, separator: str = ", ") -> list[str]:
    """解析 caption 為 tag 列表，保留原始順序"""
    if not content or not content.strip():
        return []
    return [t.strip() for t in content.split(separator) if t.strip()]


def _is_noise(tag: str) -> bool:
    """判定是否為雜訊 tag"""
    if len(tag) < MIN_TAG_LEN and not tag.replace("_", "").isalnum():
        return True
    if tag.lower() in NOISE_EXACT:
        return True
    for pattern, _ in NOISE_PATTERNS:
        if re.match(pattern, tag):
            return True
    return False


def _build_redundancy_removal_set(tags: list[str]) -> set[str]:
    """根據 REDUNDANCY_RULES，計算應移除的 tag 集合"""
    tag_set = {t.lower() for t in tags}
    to_remove: set[str] = set()
    for specific, generals in REDUNDANCY_RULES.items():
        if specific.lower() in tag_set:
            for g in generals:
                to_remove.add(g.lower())
    return to_remove


def filter_caption(
    content: str,
    separator: str = ", ",
    max_tags: int | None = None,
    trigger_word: str | None = None,
) -> str:
    """
    過濾 caption：去重、去冗餘、去雜訊，可選 limit 與 trigger 前綴。
    保持原始 tag 順序與大小寫。
    """
    tags = _parse_tags(content, separator)
    if not tags:
        return trigger_word.strip() if trigger_word else ""

    seen: set[str] = set()
    redundant = _build_redundancy_removal_set(tags)
    result: list[str] = []

    for t in tags:
        key = t.lower()
        if key in seen:
            continue
        if _is_noise(t):
            continue
        if key in redundant:
            continue
        seen.add(key)
        result.append(t)
        if max_tags is not None and len(result) >= max_tags:
            break

    out = separator.join(result)
    if trigger_word and trigger_word.strip():
        prefix = trigger_word.strip()
        if out:
            return f"{prefix}, {out}"
        return prefix
    return out
