"""
資料庫連線
"""
import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 既有 SQLite DB 缺少的可為空欄位 → 啟動時以 ALTER TABLE 補上（此專案無 migration 框架）。
# 僅新增 nullable 欄位，對既有資料無破壞性。
_ADDITIVE_COLUMNS: dict[str, dict[str, str]] = {
    "downloaded_resources": {
        "civitai_file_id": "VARCHAR(128)",
        "air": "VARCHAR(512)",
    },
    "generated_images": {
        "workflow_json": "TEXT",
        "source_image": "VARCHAR(512)",
        "source_mask": "VARCHAR(512)",
        "recipe_json": "TEXT",
        "recipe_sha256": "VARCHAR(64)",
        "recipe_workflow_json": "TEXT",
        "recipe_workflow_sha256": "VARCHAR(64)",
        "recipe_input_hashes_json": "TEXT",
        "recipe_resource_locks_json": "TEXT",
        "recipe_runtime_provenance_json": "TEXT",
        "recipe_reproduction_level": "VARCHAR(64)",
    },
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """建立缺少的資料表，並對既有表補上新增的 nullable 欄位（idempotent）。"""
    from app.db import models  # noqa: F401 確保 model 已註冊到 Base.metadata

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    for table, columns in _ADDITIVE_COLUMNS.items():
        if table not in existing_tables:
            continue  # create_all 已建出完整新表，無需補欄
        present = {c["name"] for c in inspector.get_columns(table)}
        for col, col_type in columns.items():
            if col not in present:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                logger.info("DB migration: added %s.%s (%s)", table, col, col_type)
