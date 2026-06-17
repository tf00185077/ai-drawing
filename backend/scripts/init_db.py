"""
初始化資料庫

create_all 只會建立尚未存在的表，不會替既有表補欄位。
ensure_columns 以 ALTER TABLE ADD COLUMN 補上 model 有、但既有 DB 缺的欄位（SQLite），
讓既有 auto_draw.db 升級到最新 schema 而不需重建。
"""
import sys
from pathlib import Path

from sqlalchemy import inspect, text

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import Base, engine
from app.db.models import GeneratedImage


def ensure_columns() -> None:
    """對既有表補上 model 定義中缺少的欄位（idempotent）"""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        existing_cols = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing_cols:
                continue
            col_type = column.type.compile(dialect=engine.dialect)
            with engine.begin() as conn:
                conn.execute(
                    text(f'ALTER TABLE {table.name} ADD COLUMN {column.name} {col_type}')
                )
            print(f"Added column {table.name}.{column.name} ({col_type})")


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    ensure_columns()
    print("Database tables created / migrated.")
