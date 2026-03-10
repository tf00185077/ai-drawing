"""
WD Tagger 共用服務
流程：WD14(0.35) → blacklist（依資料夾類型） → rating tags → limit 15 → trigger word
對指定目錄執行 tag_images_by_wd14_tagger.py 產生 .txt caption
被 watcher 與 lora_docs 共用

資料夾類型（依路徑判斷）：
- character/：人物訓練，濾除構圖/背景/髮瞳色等噪音
- style/：畫風訓練，濾除角色/系列名等
- background/：背景訓練，濾除人物/身體/服裝等
- costume/：服裝訓練，濾除背景/髮瞳色/臉部，保留服裝相關 tag
"""
import logging
import os
import subprocess
from pathlib import Path

from app.config import get_settings
from app.services.caption_filter import filter_caption

logger = logging.getLogger(__name__)

# 資料夾類型關鍵字（路徑中出現即採用該 blacklist）
FOLDER_TYPE_CHARACTER = "character"
FOLDER_TYPE_STYLE = "style"
FOLDER_TYPE_BACKGROUND = "background"
FOLDER_TYPE_COSTUME = "costume"

# rating tags：WD 輸出品質/分級 tag，所有訓練皆不需
WD_RATING_TAGS = [
    "rating:general", "rating:sensitive", "rating:questionable", "rating:explicit",
    "rating:e", "rating:s", "rating:q", "rating:g",
]
# 品質 tag：幾乎每張圖都有，無區辨性，所有 blacklist 共用
WD_QUALITY_NOISE_TAGS = ["best_quality", "masterpiece", "highres", "absurdres"]

# 人物訓練 blacklist：濾除構圖/表情/背景/髮瞳色等
WD_BLACKLIST_CHARACTER = [
    "1girl", "1boy", "solo", "looking_at_viewer", "smile", "open_mouth", "blush",
    "teeth", "upper_teeth_only", "closed_mouth", "expressionless", "portrait",
    "cowboy_shot", "close-up", "upper_body", "full_body", "sitting", "standing", "lying",
    "day", "outdoors", "indoors", "sky", "tree", "grass", "water", "pool", "poolside",
    "pool_ladder", "simple_background", "white_background", "blurry_background",
    "transparent_background", "depth_of_field", "nose", "lips", "mouth", "forehead",
    "black_hair", "blonde_hair", "brown_hair", "blue_hair", "red_hair", "white_hair",
    "grey_hair", "green_hair", "purple_hair", "pink_hair", "orange_hair", "aqua_hair",
    "black_eyes", "blue_eyes", "brown_eyes", "red_eyes", "green_eyes", "purple_eyes",
    "grey_eyes", "yellow_eyes", "bangs", "ahoge", "ponytail",
]

# 畫風訓練 blacklist：濾除角色/系列/品質元資料、髮瞳色等人物特徵，保留構圖/氛圍
WD_BLACKLIST_STYLE = [
    "commentary_request", "watermark", "score_9", "score_8", "score_7",
    "official_art", "commission", "scan", "letterboxed",
    "solo", "1girl", "1boy", "looking_at_viewer",
    # 髮色瞳色（畫風學的是筆觸/色調，非角色特徵）
    "black_hair", "blonde_hair", "brown_hair", "blue_hair", "red_hair", "white_hair",
    "grey_hair", "green_hair", "purple_hair", "pink_hair", "orange_hair", "aqua_hair",
    "black_eyes", "blue_eyes", "brown_eyes", "red_eyes", "green_eyes", "purple_eyes",
    "grey_eyes", "yellow_eyes", "bangs", "ahoge", "ponytail",
]

# 服裝訓練 blacklist：濾除背景/髮瞳色/臉部，保留服裝 tag（dress、skirt、school_uniform 等）
WD_BLACKLIST_COSTUME = [
    "1girl", "1boy", "solo", "looking_at_viewer", "smile", "open_mouth", "blush", "teeth",
    "upper_teeth_only", "closed_mouth", "expressionless", "portrait", "close-up",
    # 姿勢
    "cowboy_shot", "upper_body", "full_body", "sitting", "standing", "lying",
    "day", "outdoors", "indoors", "sky", "tree", "grass", "water", "pool", "poolside",
    "simple_background", "white_background", "blurry_background", "transparent_background",
    "depth_of_field", "nose", "lips", "mouth", "forehead",
    # 髮色瞳色
    "black_hair", "blonde_hair", "brown_hair", "blue_hair", "red_hair", "white_hair",
    "grey_hair", "green_hair", "purple_hair", "pink_hair", "orange_hair", "aqua_hair",
    "black_eyes", "blue_eyes", "brown_eyes", "red_eyes", "green_eyes", "purple_eyes",
    "grey_eyes", "yellow_eyes", "bangs", "ahoge", "ponytail",
    # 身體（服裝訓練焦點在衣著，非體型）
    "breasts", "large_breasts", "medium_breasts", "small_breasts", "flat_chest",
    "commentary_request", "watermark", "official_art", "scan", "letterboxed",
]

# 背景訓練 blacklist：濾除所有人物/身體/服裝相關
WD_BLACKLIST_BACKGROUND = [
    "1girl", "1boy", "2girls", "2boys", "solo", "male_focus", "female_focus",
    "looking_at_viewer", "portrait", "cowboy_shot", "close-up", "upper_body", "full_body",
    "sitting", "standing", "lying", "smile", "open_mouth", "blush", "teeth",
    "hair", "long_hair", "short_hair", "black_hair", "blonde_hair", "brown_hair",
    "blue_hair", "red_hair", "eyes", "black_eyes", "blue_eyes", "brown_eyes",
    "breasts", "large_breasts", "medium_breasts", "small_breasts", "flat_chest",
    "nose", "lips", "mouth", "forehead", "bangs", "ahoge", "ponytail",
    "school_uniform", "serafuku", "dress", "shirt", "skirt", "panties", "bra",
    "gloves", "thighhighs", "necklace", "earrings", "ribbon", "bow",
    "simple_background", "white_background", "blurry_background",
]

# 預設（路徑未符合 character/style/background 時）：同人物訓練
WD_BLACKLIST_DEFAULT = WD_BLACKLIST_CHARACTER


def resolve_folder_type(image_dir: Path) -> str:
    """
    依路徑判斷訓練類型，回傳 "character" | "style" | "background" | "costume" | "default"。
    檢查 path.parts 中是否包含對應資料夾名。
    優先順序：character > style > costume > background（先匹配到的優先）。
    """
    parts = [p.lower() for p in Path(image_dir).resolve().parts]
    if FOLDER_TYPE_CHARACTER in parts:
        return FOLDER_TYPE_CHARACTER
    if FOLDER_TYPE_STYLE in parts:
        return FOLDER_TYPE_STYLE
    if FOLDER_TYPE_COSTUME in parts:
        return FOLDER_TYPE_COSTUME
    if FOLDER_TYPE_BACKGROUND in parts:
        return FOLDER_TYPE_BACKGROUND
    return "default"


def _get_blacklist_for_folder(image_dir: Path) -> list[str]:
    """依資料夾類型回傳對應 blacklist（不含 rating，rating 會另外併入）"""
    folder_type = resolve_folder_type(image_dir)
    if folder_type == FOLDER_TYPE_CHARACTER:
        return WD_BLACKLIST_CHARACTER.copy()
    if folder_type == FOLDER_TYPE_STYLE:
        return WD_BLACKLIST_STYLE.copy()
    if folder_type == FOLDER_TYPE_COSTUME:
        return WD_BLACKLIST_COSTUME.copy()
    if folder_type == FOLDER_TYPE_BACKGROUND:
        return WD_BLACKLIST_BACKGROUND.copy()
    return WD_BLACKLIST_DEFAULT.copy()


def _apply_caption_filter(image_dir: Path) -> None:
    """對目錄內所有 .txt 套用 caption 過濾（去重、冗餘、雜訊、limit、trigger）"""
    settings = get_settings()
    root = Path(image_dir).resolve()
    for txt_path in root.rglob("*.txt"):
        try:
            content = txt_path.read_text(encoding="utf-8")
            filtered = filter_caption(
                content,
                max_tags=settings.wd_tag_limit,
                trigger_word=settings.wd_trigger_word or None,
            )
            if filtered != content:
                txt_path.write_text(filtered, encoding="utf-8")
                logger.debug("已過濾 caption: %s", txt_path.name)
        except Exception as e:
            logger.warning("過濾 caption 失敗 %s: %s", txt_path, e)


def run_wd_tagger(image_dir: Path) -> None:
    """
    對指定目錄執行 WD Tagger，產生 .txt caption。
    image_dir 為絕對路徑。
    """
    settings = get_settings()
    sd_scripts = Path(settings.sd_scripts_path)
    script = sd_scripts / "finetune" / "tag_images_by_wd14_tagger.py"

    if not script.exists():
        logger.warning("WD Tagger 腳本不存在: %s，略過標註", script)
        return

    python_exe = (settings.sd_scripts_python or "").strip() or "python"
    folder_type = resolve_folder_type(image_dir)
    blacklist = _get_blacklist_for_folder(image_dir)
    undesired = ",".join(blacklist + WD_RATING_TAGS + WD_QUALITY_NOISE_TAGS)
    logger.debug("WD Tagger 路徑 %s → 類型 %s，blacklist 共 %d 項", image_dir, folder_type, len(blacklist))

    cmd = [
        python_exe,
        str(script),
        "--onnx",
        "--repo_id", "SmilingWolf/wd-swinv2-tagger-v3",
        "--batch_size", "4",
        "--thresh", "0.7",
        "--undesired_tags", undesired,
        "--recursive",
        str(Path(image_dir).resolve()),
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(sd_scripts) + os.pathsep + env.get("PYTHONPATH", "")

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(sd_scripts),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            logger.error("WD Tagger 執行失敗: %s", proc.stderr or proc.stdout)
        else:
            _apply_caption_filter(image_dir)
            logger.info("WD Tagger 完成: %s", image_dir)
    except subprocess.TimeoutExpired:
        logger.error("WD Tagger 逾時: %s", image_dir)
    except Exception as e:
        logger.error("WD Tagger 錯誤: %s", e)
