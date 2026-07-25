"""Build/check the reviewed static comma-atomic curation worksheet.

This is an offline repository-maintenance tool. Runtime never imports it and
never translates or guesses display labels.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.core.comma_atomic_migration import (  # noqa: E402
    CURATION_RELATIVE,
    REGISTRY_RELATIVE,
    allocate_derived_id,
    canonical_json_bytes,
    provenance_identity,
    sha256_text,
)


# Human-reviewed token decisions where a shared source label would be
# semantically insufficient. Equivalent tokens intentionally reuse a label.
TOKEN_NAME_ZH = {
    # Quality and ratings
    "masterpiece": "傑作",
    "best quality": "最佳品質",
    "amazing quality": "驚艷品質",
    "very aesthetic": "高度美感",
    "newest": "最新風格",
    "absurdres": "超高解析度",
    "highres": "高解析度",
    "score_9": "評分九",
    "score_8_up": "評分八以上",
    "score_7_up": "評分七以上",
    "source_anime": "動漫來源",
    # Clothing: deliberately distinct per garment/token.
    "shirt": "襯衫",
    "dress": "連身裙",
    "ribbon": "緞帶",
    "school uniform": "學校制服",
    "white shirt": "白襯衫",
    "white buttoned shirt": "白色鈕扣襯衫",
    "short sleeves": "短袖",
    "long sleeves": "長袖",
    "collared shirt": "有領襯衫",
    "red ribbon": "紅色緞帶",
    "neck ribbon": "頸部緞帶",
    "pinafore dress": "背心連身裙",
    "grey dress": "灰色連身裙",
    "summer uniform": "夏季制服",
    "yuigaoka school uniform": "結丘女子高中制服",
    "opaque clothes": "不透膚衣物",
    "pleated skirt": "百褶裙",
    "gym uniform": "體育服",
    "buruma": "燈籠運動短褲",
    "casual oversized sweater": "休閒寬鬆毛衣",
    "office lady suit": "女性辦公套裝",
    "tight skirt": "緊身裙",
    "maid outfit": "女僕裝",
    "camisole": "細肩帶背心",
    "tank top": "無袖背心",
    "turtleneck sweater": "高領毛衣",
    "lifting shirt": "掀起上衣",
    "biting shirt": "咬住上衣",
    "shirt over head": "上衣套過頭部",
    "shirt removed": "已脫下上衣",
    "shirt open": "敞開襯衫",
    "unbuttoned shirt": "解開鈕扣的襯衫",
    "shirt off shoulder": "上衣滑落肩膀",
    "revealing bra": "露出胸罩",
    "bra strap slipping": "胸罩肩帶滑落",
    "holding clothes": "手持脫下衣物",
    "taking off skirt": "脫下裙子",
    "pulling down pants": "拉下長褲",
    "revealing panties": "露出內褲",
    "pulling down panties": "褪下內褲",
    "panties around thighs": "內褲停在大腿",
    "hands behind back": "雙手置於背後",
    "unhooking bra": "解開胸罩扣",
    # Underwear and accessories
    "garter straps": "吊襪帶",
    "thighhighs": "大腿襪",
    "two-piece lingerie set": "兩件式內衣套裝",
    "lingerie": "性感內衣",
    "matching underwear": "成套內衣",
    "bra and panties": "胸罩與內褲",
    "black bra": "黑色胸罩",
    "black panties": "黑色內褲",
    "white bra": "白色胸罩",
    "white panties": "白色內褲",
    "red bra": "紅色胸罩",
    "red panties": "紅色內褲",
    "pink bra": "粉紅色胸罩",
    "pink panties": "粉紅色內褲",
    "purple bra": "紫色胸罩",
    "purple panties": "紫色內褲",
    "blue bra": "藍色胸罩",
    "blue panties": "藍色內褲",
    "pastel pink bra": "淺粉色胸罩",
    "pastel pink panties": "淺粉色內褲",
    "mint green bra": "薄荷綠胸罩",
    "mint green panties": "薄荷綠內褲",
    # Common body/expression/camera tokens
    "curvy": "曲線豐滿",
    "thick thighs": "豐滿大腿",
    "blonde hair": "金髮",
    "dark skin": "深色皮膚",
    "muscular male": "肌肉男性",
    "young boy": "少年",
    "cute male": "可愛男性",
    "old man": "老年男性",
    "wrinkled skin": "皺紋皮膚",
    "piercings": "穿環飾品",
    "dyed hair": "染髮",
    "full face": "完整臉部",
    "male focus": "男性焦點",
    "profile": "側面輪廓",
    "side view": "側面視角",
    "full body": "全身",
    "close-up": "特寫",
    "face focus": "臉部焦點",
    "from above": "俯視",
    "from below": "仰視",
    "upper body close-up": "上半身特寫",
    "breasts visible": "可見胸部",
    "breasts focus": "胸部焦點",
    "cowboy shot": "牛仔構圖",
    "thighs visible": "可見大腿",
    "wide shot": "廣角全景",
    "surprised": "驚訝",
    "wide eyes": "睜大雙眼",
    "blush": "臉紅",
    "embarrassed": "尷尬害羞",
    "crying": "哭泣",
    "tears": "淚水",
    "smile": "微笑",
    "happy": "開心",
    "looking away": "移開視線",
    "closed eyes": "閉眼",
    "heart eyes": "愛心眼",
    "expressionless": "面無表情",
    "tongue out": "吐舌",
    "(tongue out:1.4)": "加權吐舌",
    "drooling": "流口水",
    "blank stare": "空洞凝視",
    "seductive smile": "誘惑微笑",
    "naughty face": "調皮表情",
    "furrowed brow": "皺眉",
    "smirk": "壞笑",
    "v-shaped eyebrows": "V 字眉",
    "(licking lips:1.4)": "加權舔唇",
    "teasing smile": "挑逗微笑",
    "seductively smiling": "誘惑地微笑",
    "proud": "自信得意",
    "shy": "害羞",
    "lewd": "淫蕩表情",
    "lustful": "情慾表情",
    # Environment/effects
    "love hotel": "愛情旅館",
    "pink room": "粉紅房間",
    "black bed": "黑色床鋪",
    "rei no pool": "例之泳池",
    "poolside": "泳池邊",
    "panting": "喘息",
    "breath steam": "呼吸白霧",
    "breathing steam visible": "可見呼吸白霧",
    "saliva trail": "唾液牽絲",
    "sweaty": "滿身汗水",
    "glistening skin": "泛光肌膚",
    "heart symbol": "愛心符號",
    "floating hearts": "漂浮愛心",
    "after sex": "性交後",
    "disheveled": "凌亂儀容",
    # Negative quality/anatomy tokens
    "lowres": "低解析度",
    "worst quality": "最差品質",
    "low quality": "低品質",
    "normal quality": "普通品質",
    "bad anatomy": "錯誤人體結構",
    "bad hands": "錯誤手部",
    "mutated hands": "變形手部",
    "poorly drawn hands": "手部繪製不良",
    "backwards hands": "手掌方向錯誤",
    "missing fingers": "手指缺失",
    "extra fingers": "多餘手指",
    "extra digit": "多餘指頭",
    "extra digits": "多餘指頭",
    "fewer digits": "指頭數量不足",
    "extra limbs": "多餘肢體",
    "extra arms": "多餘手臂",
    "extra legs": "多餘腿部",
    "extra hands": "多餘手掌",
    "extra feet": "多餘腳部",
    "missing legs": "腿部缺失",
    "missing arms": "手臂缺失",
    "disconnected limbs": "肢體斷裂",
    "deformed": "身體變形",
    "multiple heads": "多個頭部",
    "two heads": "兩個頭部",
    "disembodied head": "無身體頭部",
    "floating head": "漂浮頭部",
    "amputee": "肢體截斷",
    "text": "文字",
    "english text": "英文文字",
    "chinese text": "中文字",
    "error": "畫面錯誤",
    "cropped": "裁切不完整",
    "blurry": "模糊",
    "jpeg artifacts": "JPEG 壓縮瑕疵",
    "signature": "簽名",
    "watermark": "浮水印",
    "artist name": "藝術家名稱",
    "username": "使用者名稱",
    "twitter username": "推特使用者名稱",
    "patreon username": "Patreon 使用者名稱",
    "weibo username": "微博使用者名稱",
    "ugly": "醜陋",
    "monochrome": "單色",
    "duplicate": "重複物件",
}


def _has_cjk(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value))


def _curated_name(source_name: str, raw_segment: str, segment_index: int) -> str:
    token = raw_segment.strip()
    selected = TOKEN_NAME_ZH.get(token.casefold())
    if selected:
        return selected
    source_label = source_name.strip() if _has_cjk(source_name) else "原子提示詞"
    return f"{source_label}・第 {segment_index + 1} 詞（{token}）"


def _source_categories(root: Path) -> list[dict[str, object]]:
    live = [
        json.loads(path.read_text(encoding="utf-8"))
        for polarity in ("positive", "negative")
        for path in sorted((root / polarity).glob("*.json"))
    ]
    if any(
        "," in entry["prompt"]
        for category in live
        for entry in category["entries"]
    ):
        return live

    rollback_path = (
        root
        / ".comma-atomic-rollbacks"
        / "comma-atomic-v1"
        / "rollback.json"
    )
    rollback = json.loads(rollback_path.read_text(encoding="utf-8"))
    return [
        json.loads(base64.b64decode(record["base64"]))
        for relative, record in sorted(rollback["preimages"].items())
        if relative.startswith(("positive/", "negative/"))
    ]


def build_payloads(root: Path) -> tuple[dict[str, object], dict[str, object]]:
    records: list[dict[str, object]] = []
    expansions: list[dict[str, object]] = []
    categories = sorted(
        _source_categories(root),
        key=lambda item: (item["polarity"], item["id"]),
    )
    for category in categories:
        polarity = category["polarity"]
        occupied = {
            entry["id"]: None
            for entry in category["entries"]
            if "," not in entry["prompt"]
        }
        for entry in category["entries"]:
            source_prompt = entry["prompt"]
            if "," not in source_prompt:
                continue
            source_prompt_hash = sha256_text(source_prompt)
            derived: list[dict[str, str]] = []
            for segment_index, raw_segment in enumerate(source_prompt.split(",")):
                identity = provenance_identity(
                    polarity=polarity,
                    category_id=category["id"],
                    source_entry_id=entry["id"],
                    source_prompt_sha256=source_prompt_hash,
                    segment_index=segment_index,
                    raw_segment=raw_segment,
                )
                derived_id = allocate_derived_id(
                    source_entry_id=entry["id"],
                    raw_segment=raw_segment,
                    identity_sha256=identity,
                    occupied=occupied,
                )
                name_zh = _curated_name(
                    entry["name_zh"], raw_segment, segment_index
                )
                records.append(
                    {
                        "polarity": polarity,
                        "category_id": category["id"],
                        "source_entry_id": entry["id"],
                        "source_prompt_sha256": source_prompt_hash,
                        "segment_index": segment_index,
                        "raw_segment": raw_segment,
                        "name_zh": name_zh,
                        "description_zh": (
                            f"經人工拆分審閱的原子提示詞「{raw_segment.strip()}」，"
                            f"來源為「{entry['name_zh']}」。"
                        ),
                        "aliases": [raw_segment.strip()],
                        "keywords": [
                            "comma-atomic",
                            polarity,
                            category["id"],
                        ],
                        "derived_entry_id": derived_id,
                        "reviewed": True,
                    }
                )
                derived.append(
                    {
                        "polarity": polarity,
                        "category_id": category["id"],
                        "entry_id": derived_id,
                    }
                )
            expansions.append(
                {
                    "source": {
                        "polarity": polarity,
                        "category_id": category["id"],
                        "entry_id": entry["id"],
                    },
                    "derived": derived,
                }
            )
    return (
        {
            "schema_version": 1,
            "review_status": "reviewed",
            "record_count": len(records),
            "records": records,
        },
        {
            "schema_version": 1,
            "review_status": "reviewed",
            "expansion_count": len(expansions),
            "expansions": expansions,
        },
    )


def _record_key(record: dict[str, object]) -> tuple[object, ...]:
    return (
        record["polarity"],
        record["category_id"],
        record["source_entry_id"],
        record["source_prompt_sha256"],
        record["segment_index"],
    )


def validate_reviewed_payloads(
    actual_curation: dict[str, object],
    actual_registry: dict[str, object],
    expected_curation: dict[str, object],
    expected_registry: dict[str, object],
) -> list[str]:
    errors: list[str] = []
    actual_records = actual_curation.get("records", [])
    expected_records = expected_curation["records"]
    if (
        actual_curation.get("review_status") != "reviewed"
        or actual_curation.get("record_count") != 532
        or len(actual_records) != 532
    ):
        errors.append("curation must contain exactly 532 reviewed records")
    actual_by_key = {_record_key(record): record for record in actual_records}
    expected_by_key = {_record_key(record): record for record in expected_records}
    if len(actual_by_key) != 532:
        errors.append("curation contains duplicate source/provenance records")
    if set(actual_by_key) != set(expected_by_key):
        errors.append("curation source/provenance coverage drifted")
    immutable_fields = (
        "polarity",
        "category_id",
        "source_entry_id",
        "source_prompt_sha256",
        "segment_index",
        "raw_segment",
        "derived_entry_id",
    )
    for key, expected in expected_by_key.items():
        actual = actual_by_key.get(key)
        if actual is None:
            continue
        if any(actual.get(field) != expected.get(field) for field in immutable_fields):
            errors.append(f"curation immutable projection drifted: {key}")
            continue
        if actual.get("reviewed") is not True:
            errors.append(f"curation record is unresolved: {key}")
        name_zh = str(actual.get("name_zh", "")).strip()
        if not name_zh or not _has_cjk(name_zh):
            errors.append(f"curation name_zh is not reviewed Chinese: {key}")
        if not str(actual.get("description_zh", "")).strip():
            errors.append(f"curation description is blank: {key}")
        if not actual.get("aliases") or not actual.get("keywords"):
            errors.append(f"curation aliases/keywords are blank: {key}")
    def registry_map(payload: dict[str, object]) -> dict[tuple[str, str, str], object]:
        return {
            (
                expansion["source"]["polarity"],
                expansion["source"]["category_id"],
                expansion["source"]["entry_id"],
            ): expansion["derived"]
            for expansion in payload.get("expansions", [])
        }

    if (
        actual_registry.get("review_status") != "reviewed"
        or actual_registry.get("expansion_count") != 146
        or registry_map(actual_registry) != registry_map(expected_registry)
    ):
        errors.append("legacy source-ref registry drifted")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library-root", type=Path, default=REPO_ROOT / "prompt_library")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.library_root.resolve()
    curation, registry = build_payloads(root)
    if curation["record_count"] != 532 or registry["expansion_count"] != 146:
        raise SystemExit(
            "reviewed baseline drift: expected 532 records and 146 expansions"
        )
    if args.check:
        actual_curation = json.loads(
            (root / CURATION_RELATIVE).read_text(encoding="utf-8")
        )
        actual_registry = json.loads(
            (root / REGISTRY_RELATIVE).read_text(encoding="utf-8")
        )
        errors = validate_reviewed_payloads(
            actual_curation,
            actual_registry,
            curation,
            registry,
        )
        if errors:
            raise SystemExit("static curation drift: " + "; ".join(errors))
        print("static curation is deterministic: 532 records, 146 expansions")
        return 0
    parser.error(
        "checked-in reviewed curation is authoritative; use --check instead "
        "of regenerating or overwriting human corrections"
    )


if __name__ == "__main__":
    raise SystemExit(main())
