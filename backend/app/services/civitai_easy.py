"""High-level best-effort Civitai flows: source-info and generate-like.

``generate_like`` is the one-call path: import a Civitai image's generation
metadata, map it onto the proven plain generation queue, substitute the
closest local resources when the exact ones are missing (or download them
first), and submit a small batch. Every substitution and clamp is reported
back — rigor here means telling the caller what happened, not blocking.

The strict provenance pipeline (``/api/civitai-recipes/*``) remains available
for exact-reproduction audits; this module never claims exact reproduction.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.queue import submit as queue_submit
from app.core.resources import default_checkpoint, list_checkpoints, list_loras
from app.services.civitai_local_identity_ledger import local_identity_ledger
from app.services.civitai_recipe_pipeline import import_recipe
from app.services.civitai_resource_acquire import AcquireError, start_acquisition
from app.services.civitai_sampling import split_sampler_scheduler


class EasyGenerateError(Exception):
    def __init__(self, code: str, message: str, hint: str | None = None) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        detail: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.hint:
            detail["hint"] = self.hint
        return detail


def _stem(name: str) -> str:
    return Path(name.strip()).stem.casefold()


def _match_by_name(wanted: str, local_names: list[str]) -> str | None:
    """Exact filename, then extension-insensitive stem match."""
    wanted_fold = wanted.strip().casefold()
    for name in local_names:
        if name.casefold() == wanted_fold:
            return name
    wanted_stem = _stem(wanted)
    if not wanted_stem:
        return None
    for name in local_names:
        if _stem(name) == wanted_stem:
            return name
    return None


def _ledger_index(db: Session) -> dict[tuple[str, int], Any]:
    """(kind, civitai_model_version_id) → ledger entry for installed files."""
    index: dict[tuple[str, int], Any] = {}
    for entry in local_identity_ledger(db).entries:
        if not entry.availability or entry.civitai_model_version_id is None:
            continue
        if Path(entry.local_path).is_file():
            index[(entry.normalized_kind(), entry.civitai_model_version_id)] = entry
    return index


def _match_resource(resource: dict[str, Any], *, kind: str, local_names: list[str], ledger: dict) -> dict[str, Any]:
    """Match one recipe resource against local files: ledger identity first, then filename."""
    version_id = resource.get("civitai_model_version_id")
    if isinstance(version_id, int):
        entry = ledger.get((kind, version_id))
        if entry is not None:
            local_name = Path(entry.local_path).name
            if _match_by_name(local_name, local_names):
                return {"status": "exact_local", "local_name": local_name}
    name = str(resource.get("name") or "")
    if name:
        matched = _match_by_name(name, local_names)
        if matched:
            return {"status": "name_match_local", "local_name": matched}
    if isinstance(version_id, int) or isinstance(resource.get("civitai_model_id"), int):
        return {
            "status": "missing_downloadable",
            "civitai_model_version_id": version_id,
            "civitai_model_id": resource.get("civitai_model_id"),
        }
    return {"status": "missing_no_identity"}


def _clamp(value: Any, low: float, high: float, field: str, warnings: list[str]) -> Any:
    if not isinstance(value, (int, float)):
        return None
    if value < low or value > high:
        clamped = min(max(value, low), high)
        warnings.append(f"{field}={value} 超出可用範圍，已調整為 {clamped}")
        return int(clamped) if isinstance(value, int) else clamped
    return value


def plan_generation(recipe: dict[str, Any], *, db: Session) -> dict[str, Any]:
    """Tiered resource plan: exact local → filename match → downloadable → default."""
    settings = get_settings()
    local_checkpoints = list_checkpoints(settings)
    local_loras = list_loras(settings)
    ledger = _ledger_index(db)

    substitutions: list[str] = []
    warnings: list[str] = []
    needs_download: list[dict[str, Any]] = []

    checkpoint_name: str | None = None
    lora_specs: list[dict[str, Any]] = []
    for resource in recipe.get("resources", []):
        kind = str(resource.get("kind") or "")
        name = str(resource.get("name") or "")
        if kind == "checkpoint":
            match = _match_resource(resource, kind="checkpoint", local_names=local_checkpoints, ledger=ledger)
            if match["status"] in {"exact_local", "name_match_local"}:
                checkpoint_name = match["local_name"]
            elif match["status"] == "missing_downloadable":
                needs_download.append({"kind": "checkpoint", "name": name, **{k: v for k, v in match.items() if k.startswith("civitai")}})
            else:
                warnings.append(f"原作 checkpoint「{name}」沒有 Civitai 識別資訊，無法自動下載")
        elif kind == "lora":
            match = _match_resource(resource, kind="lora", local_names=local_loras, ledger=ledger)
            if match["status"] in {"exact_local", "name_match_local"}:
                spec: dict[str, Any] = {"name": match["local_name"]}
                if isinstance(resource.get("strength_model"), (int, float)):
                    spec["strength_model"] = resource["strength_model"]
                if isinstance(resource.get("strength_clip"), (int, float)):
                    spec["strength_clip"] = resource["strength_clip"]
                lora_specs.append(spec)
            elif match["status"] == "missing_downloadable":
                needs_download.append({"kind": "lora", "name": name, **{k: v for k, v in match.items() if k.startswith("civitai")}})
            else:
                warnings.append(f"LoRA「{name}」沒有 Civitai 識別資訊，將略過（畫風可能與原作不同）")
        elif kind in {"embedding", "vae", "controlnet", "upscaler", "detailer"}:
            warnings.append(f"{kind}「{name}」不在 best-effort 流程處理範圍，已略過")

    if checkpoint_name is None:
        fallback = default_checkpoint(settings)
        original = next((str(r.get("name") or "") for r in recipe.get("resources", []) if r.get("kind") == "checkpoint"), None)
        if fallback:
            checkpoint_name = fallback
            if original:
                substitutions.append(f"checkpoint：原作用「{original}」，本地沒有，暫以「{fallback}」代替（下載完成後重呼叫可用原模型）")
            else:
                substitutions.append(f"來源沒有標註 checkpoint，使用本地預設「{fallback}」")
        else:
            raise EasyGenerateError(
                "no_local_checkpoint",
                "本地沒有任何 checkpoint 可用",
                hint="先用 civitai_resource_acquire 下載一個 checkpoint，或確認外接硬碟已掛載",
            )

    sampling = recipe.get("sampling") or {}
    sampler_name: str | None = None
    scheduler: str | None = None
    if isinstance(sampling.get("sampler"), str) and sampling["sampler"].strip():
        sampler_name, scheduler = split_sampler_scheduler(sampling["sampler"])
    if isinstance(sampling.get("scheduler"), str) and sampling["scheduler"].strip():
        scheduler = sampling["scheduler"]

    return {
        "checkpoint": checkpoint_name,
        "loras": lora_specs,
        "sampler_name": sampler_name,
        "scheduler": scheduler,
        "steps": _clamp(sampling.get("steps"), 1, 150, "steps", warnings),
        "cfg": _clamp(sampling.get("cfg"), 1.0, 30.0, "cfg", warnings),
        "width": _clamp(sampling.get("width"), 256, 2048, "width", warnings),
        "height": _clamp(sampling.get("height"), 256, 2048, "height", warnings),
        "seed": sampling.get("seed"),
        "needs_download": needs_download,
        "substitutions": substitutions,
        "warnings": warnings,
    }


def source_info(locator: int | str, *, db: Session, transport: Any | None = None) -> dict[str, Any]:
    """Read-only preview: what the source image used and what is available locally."""
    imported = _import(locator, transport)
    recipe = imported["recipe"]
    plan = plan_generation(recipe, db=db)
    return {
        "source": recipe.get("source", {}),
        "prompt": recipe.get("base_prompt"),
        "negative_prompt": recipe.get("negative_prompt"),
        "sampling": recipe.get("sampling"),
        "resources": recipe.get("resources", []),
        "local_plan": {key: plan[key] for key in ("checkpoint", "loras", "substitutions", "warnings", "needs_download")},
        "next_step": (
            "可直接呼叫 civitai_generate_like 生圖；prompt 參數會取代原 prompt（保留原 sampler/steps/cfg/尺寸），"
            "needs_download 非空時預設會先自動下載缺的模型"
        ),
    }


def generate_like(
    locator: int | str,
    *,
    db: Session,
    prompt: str | None = None,
    negative_prompt: str | None = None,
    batch_size: int | None = None,
    seed: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
    width: int | None = None,
    height: int | None = None,
    checkpoint: str | None = None,
    download_missing: bool = True,
    transport: Any | None = None,
    submit_fn: Callable[[dict[str, Any]], str] | None = None,
    acquire_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Import a Civitai image's parameters, swap the prompt, and queue a batch."""
    settings = get_settings()
    imported = _import(locator, transport)
    recipe = imported["recipe"]
    plan = plan_generation(recipe, db=db)

    if plan["needs_download"] and download_missing:
        acquire = acquire_fn or (lambda ident, **kwargs: start_acquisition(ident, db=db, **kwargs))
        downloads: list[dict[str, Any]] = []
        failures: list[str] = []
        for item in plan["needs_download"]:
            identity = item.get("civitai_model_version_id") or item.get("civitai_model_id")
            try:
                downloads.append(acquire(identity))
            except AcquireError as exc:
                failures.append(f"「{item.get('name')}」無法自動下載：{exc.message}" + (f"（{exc.hint}）" if exc.hint else ""))
        if downloads:
            return {
                "status": "acquiring_resources",
                "downloads": downloads,
                "warnings": [*plan["warnings"], *failures],
                "next_step": (
                    "缺少的模型正在下載；用 civitai_resource_status 查進度，全部 installed 後重新呼叫 civitai_generate_like。"
                    "不想等下載可帶 download_missing=false，會用最接近的本地模型代替"
                ),
            }
        plan["warnings"].extend(failures)
    elif plan["needs_download"]:
        for item in plan["needs_download"]:
            plan["substitutions"].append(
                f"{item.get('kind')}「{item.get('name')}」本地沒有且 download_missing=false，"
                + ("已用替代模型" if item.get("kind") == "checkpoint" else "已略過")
            )

    final_prompt = prompt if prompt is not None else recipe.get("base_prompt")
    if not final_prompt or not str(final_prompt).strip():
        raise EasyGenerateError(
            "prompt_missing",
            "來源沒有可用的 prompt，且呼叫端未提供",
            hint="帶 prompt 參數描述你想要的畫面",
        )
    final_negative = negative_prompt if negative_prompt is not None else recipe.get("negative_prompt")

    params: dict[str, Any] = {
        "checkpoint": checkpoint or plan["checkpoint"],
        "lora": None,
        "prompt": str(final_prompt),
        "negative_prompt": final_negative,
        "seed": seed,
        "steps": steps if steps is not None else (plan["steps"] or 20),
        "cfg": cfg if cfg is not None else (plan["cfg"] or 7.0),
    }
    if plan["loras"]:
        params["loras"] = plan["loras"]
    final_width = width if width is not None else plan["width"]
    final_height = height if height is not None else plan["height"]
    if final_width:
        params["width"] = int(final_width)
    if final_height:
        params["height"] = int(final_height)
    if plan["sampler_name"]:
        params["sampler_name"] = plan["sampler_name"]
    if plan["scheduler"]:
        params["scheduler"] = plan["scheduler"]
    params["batch_size"] = max(1, min(batch_size if batch_size is not None else settings.civitai_generate_default_batch, 8))

    job_id = (submit_fn or queue_submit)(params)
    used = {key: value for key, value in params.items() if value is not None and key != "lora"}
    return {
        "status": "queued",
        "job_id": job_id,
        "used_parameters": used,
        "substitutions": plan["substitutions"],
        "warnings": plan["warnings"],
        "source": recipe.get("source", {}),
        "next_step": (
            "用 get_generation_status(job_id) 查進度；完成後會回 gallery 的 image_id/路徑。"
            "同一組參數想再抽一批可用 gallery_rerun，或改 prompt 後重呼叫本工具"
        ),
    }


def _import(locator: int | str, transport: Any | None) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if transport is not None:
        kwargs["transport"] = transport
    try:
        return import_recipe(locator, **kwargs)
    except Exception as exc:
        from app.services.civitai_acquisition import AcquisitionError

        if isinstance(exc, AcquisitionError):
            hint = None
            if exc.code == "unsupported_locator":
                hint = "接受：civitai.com/images/<id> 連結、圖片 ID 數字，或含 modelVersionId 的模型頁連結"
            raise EasyGenerateError(exc.code, str(exc), hint) from exc
        raise EasyGenerateError("import_failed", f"讀取 Civitai 圖片資訊失敗：{exc.__class__.__name__}") from exc
