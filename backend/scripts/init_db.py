"""
初始化資料庫
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import engine, Base
from app.db.models import GeneratedImage

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Database tables created.")
