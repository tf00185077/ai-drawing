"""
測試資料庫連線與 ORM
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import engine, SessionLocal
from app.db.models import GeneratedImage
from sqlalchemy import text


def main():
    ok = True

    # 1. 測試連線
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("[OK] Connection: SELECT 1 =", result.scalar())
    except Exception as e:
        print("[FAIL] Connection failed:", e)
        ok = False
        return 1

    # 2. 檢查 generated_images 表是否存在
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='generated_images'")
            )
            table = result.scalar()
            if table:
                print("[OK] Table generated_images exists")
            else:
                print("[FAIL] Table generated_images missing")
                ok = False
    except Exception as e:
        print("[FAIL] Table check failed:", e)
        ok = False

    # 3. 測試 Session 與 ORM 查詢
    try:
        db = SessionLocal()
        try:
            count = db.query(GeneratedImage).count()
            print("[OK] ORM query OK, row count:", count)
        finally:
            db.close()
    except Exception as e:
        print("[FAIL] ORM query failed:", e)
        ok = False

    print("")
    if ok:
        print("DB test passed.")
        return 0
    else:
        print("Some tests failed. Run: python backend/scripts/init_db.py")
        return 1


if __name__ == "__main__":
    sys.exit(main())
