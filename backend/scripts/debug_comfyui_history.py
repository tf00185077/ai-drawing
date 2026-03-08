"""
除錯用：取得 ComfyUI GET /history 回傳並印到 terminal。
執行：
  cd backend && python scripts/debug_comfyui_history.py        # 完整回傳（可能很長）
  cd backend && python scripts/debug_comfyui_history.py --sample   # 只印一筆結構
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.core.comfyui import ComfyUIClient


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", action="store_true", help="只印最新一筆的結構")
    args = parser.parse_args()

    settings = get_settings()
    client = ComfyUIClient(base_url=settings.comfyui_base_url)
    print("=== ComfyUI GET /history 回傳 ===\n", flush=True)
    try:
        data = client.get_full_history()
        if args.sample and data:
            # 取最新一筆（dict 順序不保證，取第一個）
            pid = next(iter(data))
            sample = {pid: data[pid]}
            print(f"（--sample：只顯示一筆 prompt_id={pid}）\n", flush=True)
            print(json.dumps(sample, indent=2, ensure_ascii=False), flush=True)
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False), flush=True)
    except Exception as e:
        print(f"Error: {e}", flush=True)
        raise


if __name__ == "__main__":
    main()
