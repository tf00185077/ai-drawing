"""
WD Tagger 共用服務
對指定目錄執行 tag_images_by_wd14_tagger.py 產生 .txt caption
被 watcher 與 lora_docs 共用
"""
import logging
import os
import subprocess
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)


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

    cmd = [
        python_exe,
        str(script),
        "--onnx",
        "--repo_id",
        "SmilingWolf/wd-swinv2-tagger-v3",
        "--batch_size",
        "4",
        "--thresh",
        "0.35",
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
            logger.info("WD Tagger 完成: %s", image_dir)
    except subprocess.TimeoutExpired:
        logger.error("WD Tagger 逾時: %s", image_dir)
    except Exception as e:
        logger.error("WD Tagger 錯誤: %s", e)
