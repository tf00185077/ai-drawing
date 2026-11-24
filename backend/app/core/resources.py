from __future__ import annotations

from pathlib import Path
from typing import Protocol


MODEL_EXTENSIONS = (".safetensors", ".ckpt", ".pth")


class ResourceSettings(Protocol):
    comfyui_checkpoints_dir: str
    comfyui_loras_dir: str
    comfyui_diffusion_models_dir: str
    comfyui_text_encoders_dir: str
    comfyui_vae_dir: str
    lora_default_checkpoint: str


def _split_dirs(paths: str) -> list[Path]:
    """Return configured model directories.

    Settings may contain a single path or comma-separated paths so ai-drawing can
    list both the existing local ComfyUI model folders and an external-disk model
    library configured through ComfyUI extra_model_paths.yaml.
    """
    return [Path(part.strip()).expanduser() for part in paths.split(",") if part.strip()]


def list_model_files(
    dir_path: Path,
    exts: tuple[str, ...] = MODEL_EXTENSIONS,
) -> list[str]:
    if not dir_path.exists() or not dir_path.is_dir():
        return []
    return sorted(
        p.name
        for p in dir_path.iterdir()
        if p.is_file() and p.suffix.lower() in exts
    )


def list_model_files_in_dirs(
    dir_paths: str,
    exts: tuple[str, ...] = MODEL_EXTENSIONS,
) -> list[str]:
    """List model filenames from one or more directories, de-duplicated.

    ComfyUI model selectors use filenames, not absolute paths. If the same file
    exists in local and external roots, return it once.
    """
    names: set[str] = set()
    for dir_path in _split_dirs(dir_paths):
        names.update(list_model_files(dir_path, exts=exts))
    return sorted(names)


def list_checkpoints(settings: ResourceSettings) -> list[str]:
    return list_model_files_in_dirs(settings.comfyui_checkpoints_dir)


def lora_catalog(settings: ResourceSettings) -> dict:
    """Root legacy files and ONE controlled AI-Drawing run level, without links.

    Ambiguous multi-root locators are excluded from selection and reported.
    Other model scanners keep their established behavior.
    """
    import hashlib, json, unicodedata
    found: dict[str, list[tuple[str, Path, dict | None]]] = {}
    raw=getattr(settings,'comfyui_loras_dir','') or getattr(settings,'comfyui_lora_dir','') or ''
    seen_roots=set()
    for root in _split_dirs(raw):
        if root.absolute() in seen_roots: continue
        seen_roots.add(root.absolute())
        if not root.is_dir() or root.is_symlink(): continue
        paths=[p for p in root.iterdir() if p.is_file() and not p.is_symlink() and p.suffix.lower() in MODEL_EXTENSIONS]
        managed=root/'AI-Drawing'
        if managed.is_dir() and not managed.is_symlink():
            for run in managed.iterdir():
                if not run.is_dir() or run.is_symlink(): continue
                paths.extend(p for p in run.iterdir() if p.is_file() and not p.is_symlink() and p.suffix.lower()=='.safetensors')
        for path in paths:
            if any(getattr(p.stat(), 'st_file_attributes',0)&0x400 for p in [path,*path.parents] if p==root or p.is_relative_to(root)): continue
            locator=path.relative_to(root).as_posix()
            owner=None
            if locator.startswith('AI-Drawing/'):
                try: owner=json.loads((path.parent/'registration.json').read_text(encoding='utf-8'))
                except (OSError,ValueError): pass
            key=unicodedata.normalize('NFC',locator).casefold()
            found.setdefault(key,[]).append((locator,path,owner))
    available=[];conflicts=[]
    def content_hash(path):
        h=hashlib.sha256()
        with path.open('rb') as f:
            for part in iter(lambda:f.read(1024*1024),b''): h.update(part)
        return h.hexdigest()
    for entries in found.values():
        if len(entries)>1:
            owners=[e[2] for e in entries]
            if any(not owner for owner in owners) or any(owner!=owners[0] for owner in owners) or len({content_hash(e[1]) for e in entries})>1:
                conflicts.append({'locator':entries[0][0],'code':'lora_locator_conflict','reason':'multiple roots have differing content or unknown ownership'})
                continue
        available.append(entries[0][0])
    return {'loras':sorted(available),'lora_conflicts':sorted(conflicts,key=lambda v:v['locator'])}


def list_loras(settings: ResourceSettings) -> list[str]:
    return lora_catalog(settings)['loras']


def list_diffusion_models(settings: ResourceSettings) -> list[str]:
    """diffusion-model 家族（如 Anima）的 UNET 檔，供 UNETLoader 使用"""
    return list_model_files_in_dirs(settings.comfyui_diffusion_models_dir)


def list_text_encoders(settings: ResourceSettings) -> list[str]:
    """text encoder 檔，供 CLIPLoader 使用"""
    return list_model_files_in_dirs(settings.comfyui_text_encoders_dir)


def list_vaes(settings: ResourceSettings) -> list[str]:
    """VAE 檔，供 VAELoader 使用"""
    return list_model_files_in_dirs(settings.comfyui_vae_dir)


def first_available_checkpoint(settings: ResourceSettings) -> str | None:
    checkpoints = list_checkpoints(settings)
    return checkpoints[0] if checkpoints else None


def default_checkpoint(settings: ResourceSettings) -> str | None:
    return first_available_checkpoint(settings) or settings.lora_default_checkpoint or None
