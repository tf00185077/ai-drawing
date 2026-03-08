"""
WD Tagger 共用服務
流程：WD14(0.35) → blacklist → rating tags → limit 15 → trigger word
對指定目錄執行 tag_images_by_wd14_tagger.py 產生 .txt caption
被 watcher 與 lora_docs 共用
"""
import logging
import os
import subprocess
from pathlib import Path

from app.config import get_settings
from app.services.caption_filter import filter_caption

logger = logging.getLogger(__name__)

# blacklist：Kohya --undesired_tags 排除
WD_BLACKLIST = [
    "solo", "looking_at_viewer", "smile", "open_mouth", "blush", "teeth",
    "upper_teeth_only", "day", "outdoors", "indoors", "sky", "tree", "grass",
    "water", "pool", "poolside", "pool_ladder", "simple_background",
    "white_background", "blurry_background", "depth_of_field", "cowboy_shot",
    "close-up", "upper_body", "full_body", "sitting", "standing", "lying",
]

# rating tags：WD 輸出品質/分級 tag，訓練不需
WD_RATING_TAGS = [
    "rating:general", "rating:sensitive", "rating:questionable", "rating:explicit",
    "rating:e", "rating:s", "rating:q", "rating:g",
]


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
    undesired = ",".join(WD_BLACKLIST + WD_RATING_TAGS)

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
