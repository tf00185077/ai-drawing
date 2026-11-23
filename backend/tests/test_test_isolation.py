"""These assertions exercise the real root conftest import boundary."""
import os
from pathlib import Path
from app.config import get_settings
from app.db import database

def test_settings_and_real_engine_are_scratch_bound_before_collection():
    root = Path(os.environ['AI_DRAWING_TEST_ROOT']).resolve()
    settings = get_settings()
    assert database.engine.url.database == ':memory:'
    for key in ('gallery_dir','output_dir','lora_train_dir','lora_train_logs_dir','comfyui_lora_dir','prompt_library_dir','file_digest_cache_path','watch_dirs'):
        assert Path(getattr(settings,key)).is_relative_to(root), key
    assert settings.comfyui_mode == 'disabled'
