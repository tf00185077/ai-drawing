"""Explicit pre-import boundary for offline pytest, never used by production."""
import os
from pathlib import Path
import tempfile


def activate():
    raw = os.environ.get('AI_DRAWING_TEST_ROOT')
    if not raw:
        raise RuntimeError('Set AI_DRAWING_TEST_ROOT to a dedicated scratch directory before pytest')
    root = Path(raw).absolute()
    temp = Path(tempfile.gettempdir()).resolve()
    # /var -> /private/var is a normal macOS temp alias; reject links at/below temp.
    resolved = root.resolve()
    if resolved == temp or not resolved.is_relative_to(temp):
        raise RuntimeError('test root must be a dedicated directory below system scratch')
    cursor = root
    while cursor.resolve() != temp:
        if cursor.is_symlink():
            raise RuntimeError('test root symlink is forbidden')
        cursor = cursor.parent
    root = resolved
    root.mkdir(parents=True, exist_ok=True)
    values = {
        'DATABASE_URL': f'sqlite:///{root / "test.db"}',
        'COMFYUI_MODE': 'disabled', 'COMFYUI_RECORD_EXTERNAL': 'false',
        'NVIDIA_WORKER_URL': '', 'NVIDIA_WORKER_DISCOVERY_ENABLED': 'false',
        'LLM_CAPTION_URL': '', 'CIVITAI_AUTHORIZATION': '',
        'LORA_DEFAULT_CHECKPOINT': '', 'SD_SCRIPTS_PYTHON': '',
        'LORA_ANIMA_QWEN3': '', 'LORA_ANIMA_VAE': '', 'LORA_ANIMA_T5_TOKENIZER_PATH': '',
        'LORA_CHECKPOINT_DIRS': str(root/'checkpoints'),
    }
    if (root/'test.db').is_symlink():
        raise RuntimeError('test database symlink is forbidden')
    for key in ('OUTPUT_DIR','GALLERY_DIR','VIDEO_STAGING_DIR','FILM_WORK_DIR','FILM_MODEL_PATH',
                'ARGUS_MLX_RUNTIME_ROOT','ARGUS_MLX_PYTHON','ARGUS_MLX_GENERATE_SCRIPT',
                'ARGUS_MLX_CHECKPOINT','ARGUS_MLX_TRANSFORMER','ARGUS_MLX_TURBO_LORA',
                'ARGUS_MLX_WORK_ROOT','ARGUS_MLX_HF_CACHE','ARGUS_MLX_FFMPEG','ARGUS_MLX_FFPROBE',
                'PROMPT_LIBRARY_DIR','FILE_DIGEST_CACHE_PATH','LORA_TRAIN_DIR','LORA_TRAIN_LOGS_DIR',
                'SD_SCRIPTS_PATH','WATCH_DIRS','CONTROLNET_DEFAULT_POSE_IMAGE',
                'COMFYUI_CHECKPOINTS_DIR','COMFYUI_LORAS_DIR','COMFYUI_LORA_DIR',
                'COMFYUI_DIFFUSION_MODELS_DIR','COMFYUI_TEXT_ENCODERS_DIR','COMFYUI_VAE_DIR',
                'COMFYUI_EMBEDDINGS_DIR','COMFYUI_CONTROLNET_DIR','COMFYUI_UPSCALE_MODELS_DIR',
                'COMFYUI_CLIP_VISION_DIR','COMFYUI_AUDIO_MODELS_DIR','COMFYUI_INPUT_DIR'):
        path = root/key.lower()
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise RuntimeError('test path escapes scratch')
        values[key] = str(path)
    os.environ.update(values)
    os.environ['AI_DRAWING_TEST_ROOT'] = str(root)
    os.environ['AI_DRAWING_TEST_CONFIGURED'] = str(root)
    return root


def run_script(script, *, scratch, python=None, args=(), overrides=None):
    """Run an owned fixture in a new guarded interpreter with an env allowlist."""
    import subprocess
    import sys
    file = Path(scratch)/'offline-child.py'
    file.write_text(script)
    keys = ('PATH','TMPDIR','PYTEST_DISABLE_PLUGIN_AUTOLOAD','PYTHONDONTWRITEBYTECODE',
            'AI_DRAWING_TEST_ROOT','AI_DRAWING_TEST_CONFIGURED','DATABASE_URL','GALLERY_DIR')
    env = {k:os.environ[k] for k in keys if k in os.environ}
    env.update(overrides or {})
    runner=Path(__file__).resolve().parents[1]/'tools/offline_pytest.py'
    return subprocess.run([python or sys.executable,'-I','-S','-B',str(runner),'--script',str(file),*args],env=env,capture_output=True,text=True,timeout=30)
