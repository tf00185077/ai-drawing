"""CIV-E canonical gallery recipe provenance bundle helpers."""
from __future__ import annotations

import hashlib
import json
import string
from pathlib import Path
from typing import Any, Mapping, NoReturn

from pydantic import ValidationError

from app.schemas.generation_recipe import GenerationRecipe, ReproductionLevel, RuntimeProvenance


class ProvenanceValidationError(ValueError):
    """Fail-closed, stable validation error for persisted provenance."""

    def __init__(self, code: str, field: str, message: str) -> None:
        self.code = code
        self.field = field
        self.message = message
        super().__init__(message)

    def detail(self) -> dict[str, str]:
        return {"error": self.code, "field": self.field, "message": self.message}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _fail(code: str, field: str, message: str) -> NoReturn:
    raise ProvenanceValidationError(code, field, message)


def _as_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail("provenance_invalid", field, f"{field} must be an object")
    return dict(value)


def _as_list(value: Any, field: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, Mapping) for item in value):
        _fail("provenance_invalid", field, f"{field} must be a list of objects")
    return [dict(item) for item in value]


def _validated_recipe(recipe: Any) -> dict[str, Any]:
    try:
        parsed = GenerationRecipe.model_validate(recipe)
    except ValidationError as exc:
        _fail("recipe_schema_invalid", "recipe", str(exc))
    return parsed.model_dump(mode="json", exclude_none=True)


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in string.hexdigits for char in value)


def _nonempty_path(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_identity(recipe: dict[str, Any], locks: list[dict[str, Any]]) -> None:
    resources = recipe.get("resources", [])
    if len(locks) != len(resources):
        _fail("resource_lock_missing", "resource_locks", "every recipe resource requires exactly one ordered lock")
    for index, resource in enumerate(resources):
        lock = locks[index]
        field = f"resource_locks[{index}]"
        if lock.get("index") != index:
            _fail("resource_lock_identity_mismatch", field, "lock index must match recipe resource order")
        if lock.get("kind") != resource.get("kind"):
            _fail("resource_lock_identity_mismatch", f"{field}.kind", "lock kind does not match recipe resource")
        if not _is_sha256(lock.get("sha256")):
            _fail("resource_lock_sha256_invalid", f"{field}.sha256", "resource lock sha256 must be a 64-character hexadecimal digest")
        for identity in ("sha256", "civitai_model_id", "civitai_model_version_id", "civitai_file_id", "air"):
            expected = resource.get(identity)
            actual = lock.get(identity)
            if expected is not None and actual != expected:
                _fail("resource_lock_identity_mismatch", f"{field}.{identity}", "lock identity does not match recipe resource")
        if not _nonempty_path(lock.get("local_path")):
            _fail("resource_lock_local_path_missing", f"{field}.local_path", "resource lock requires a local_path")


def _validate_inputs(recipe: dict[str, Any], inputs: list[dict[str, Any]]) -> None:
    by_reference: dict[str, tuple[int, dict[str, Any]]] = {}
    for index, item in enumerate(inputs):
        reference = item.get("reference")
        if not isinstance(reference, str) or not reference or reference in by_reference:
            _fail("input_manifest_invalid", f"input_hashes[{index}].reference", "input reference must be unique and non-empty")
        if not _is_sha256(item.get("sha256")):
            _fail("input_manifest_invalid", f"input_hashes[{index}].sha256", "input sha256 must be a 64-character hexadecimal digest")
        by_reference[reference] = (index, item)
    for index, item in enumerate(recipe.get("inputs", [])):
        found = by_reference.get(item["reference"])
        if found is None:
            _fail("required_input_missing", f"inputs[{index}]", "recipe input has no persisted hash manifest")
        manifest_index, manifest = found
        field = f"input_hashes[{manifest_index}]"
        if manifest.get("required") is not True:
            _fail("required_input_manifest_invalid", f"{field}.required", "recipe input manifest must be required=true")
        if not _nonempty_path(manifest.get("local_path")):
            _fail("required_input_local_path_missing", f"{field}.local_path", "recipe input manifest requires a local_path")
        if manifest["sha256"].lower() != item["sha256"]:
            _fail("input_hash_mismatch", f"{field}.sha256", "input manifest hash does not match recipe input")


def _validate_workflow_binding(recipe: dict[str, Any], workflow: dict[str, Any], workflow_sha: str) -> None:
    recipe_workflow = recipe.get("workflow")
    if not isinstance(recipe_workflow, Mapping):
        _fail("workflow_snapshot_missing", "recipe.workflow", "recipe must contain a CIV-D workflow snapshot")
    snapshot = recipe_workflow.get("snapshot")
    if not isinstance(snapshot, Mapping):
        _fail("workflow_snapshot_missing", "recipe.workflow.snapshot", "recipe workflow snapshot must be an object")
    snapshot_sha = recipe_workflow.get("snapshot_sha256")
    if not _is_sha256(snapshot_sha):
        _fail("workflow_snapshot_digest_missing", "recipe.workflow.snapshot_sha256", "recipe workflow snapshot requires a SHA-256 digest")
    if canonical_sha256(dict(snapshot)) != snapshot_sha.lower():
        _fail("workflow_snapshot_digest_mismatch", "recipe.workflow.snapshot_sha256", "recipe workflow snapshot digest does not match its canonical content")
    if dict(snapshot) != workflow or snapshot_sha.lower() != workflow_sha:
        _fail("workflow_snapshot_binding_mismatch", "recipe.workflow", "recipe workflow snapshot does not match the stored workflow")


def _validate_bundle(bundle: Mapping[str, Any], *, verify_files: bool = False) -> dict[str, Any]:
    raw = dict(bundle)
    recipe = _validated_recipe(raw.get("recipe"))
    workflow = _as_object(raw.get("workflow"), "workflow")
    inputs = _as_list(raw.get("input_hashes"), "input_hashes")
    locks = _as_list(raw.get("resource_locks"), "resource_locks")
    runtime = _as_object(raw.get("runtime_provenance"), "runtime_provenance")
    try:
        runtime = RuntimeProvenance.model_validate(runtime).model_dump(mode="json", exclude_none=True)
    except ValidationError as exc:
        _fail("runtime_provenance_invalid", "runtime_provenance", str(exc))
    level = raw.get("reproduction_level")
    try:
        level = ReproductionLevel(level).value
    except (TypeError, ValueError):
        _fail("provenance_invalid", "reproduction_level", "reproduction_level must be a supported value")
    if runtime != recipe.get("runtime"):
        _fail("runtime_provenance_mismatch", "runtime_provenance", "runtime provenance must match recipe runtime")
    _validate_identity(recipe, locks)
    _validate_inputs(recipe, inputs)
    recipe_sha = canonical_sha256(recipe)
    workflow_sha = canonical_sha256(workflow)
    _validate_workflow_binding(recipe, workflow, workflow_sha)
    if raw.get("recipe_sha256") not in (None, recipe_sha):
        _fail("recipe_sha256_mismatch", "recipe_sha256", "recipe digest does not match canonical snapshot")
    if raw.get("workflow_sha256") not in (None, workflow_sha):
        _fail("workflow_sha256_mismatch", "workflow_sha256", "workflow digest does not match canonical snapshot")
    normalized = {
        "schema_version": "1.0",
        "recipe": recipe,
        "recipe_sha256": recipe_sha,
        "workflow": workflow,
        "workflow_sha256": workflow_sha,
        "input_hashes": inputs,
        "resource_locks": locks,
        "runtime_provenance": runtime,
        "reproduction_level": level,
    }
    if verify_files:
        _verify_local_files(normalized)
    return normalized


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_local_files(bundle: dict[str, Any]) -> None:
    for index, item in enumerate(bundle["input_hashes"]):
        if not item.get("required"):
            continue
        path = Path(item["local_path"])
        field = f"input_hashes[{index}]"
        if not path.is_file():
            _fail("required_input_missing", field, "required input file is missing")
        try:
            actual = _file_sha256(path)
        except OSError:
            _fail("required_input_missing", field, "required input file cannot be read")
        if actual != item["sha256"].lower():
            _fail("input_hash_mismatch", field, "required input file digest does not match manifest")
    for index, lock in enumerate(bundle["resource_locks"]):
        path = Path(lock["local_path"])
        field = f"resource_locks[{index}]"
        if not path.is_file():
            _fail("resource_lock_missing", field, "locked local resource is missing")
        try:
            actual = _file_sha256(path)
        except OSError:
            _fail("resource_lock_missing", field, "locked local resource cannot be read")
        if actual != lock["sha256"].lower():
            _fail("resource_lock_hash_mismatch", field, "locked local resource digest does not match manifest")


def build_recipe_provenance_bundle(*, recipe: Any, workflow: Any, input_hashes: Any,
                                   resource_locks: Any, runtime_provenance: Any,
                                   reproduction_level: str) -> dict[str, Any]:
    """Build a canonical bundle; caller receives no partial result on failure."""
    return _validate_bundle({
        "recipe": recipe,
        "workflow": workflow,
        "input_hashes": input_hashes,
        "resource_locks": resource_locks,
        "runtime_provenance": runtime_provenance,
        "reproduction_level": reproduction_level,
    })


def bundle_from_record(record: Any, *, verify_files: bool = False) -> dict[str, Any]:
    """Read and revalidate all persisted columns before export or rerun."""
    columns = {
        "recipe": "recipe_json", "recipe_sha256": "recipe_sha256",
        "workflow": "recipe_workflow_json", "workflow_sha256": "recipe_workflow_sha256",
        "input_hashes": "recipe_input_hashes_json", "resource_locks": "recipe_resource_locks_json",
        "runtime_provenance": "recipe_runtime_provenance_json", "reproduction_level": "recipe_reproduction_level",
    }
    raw: dict[str, Any] = {}
    for key, column in columns.items():
        value = getattr(record, column, None)
        if value is None:
            _fail("recipe_bundle_missing", column, "gallery record has no complete recipe provenance bundle")
        if key in {"recipe_sha256", "workflow_sha256", "reproduction_level"}:
            raw[key] = value
            continue
        try:
            raw[key] = json.loads(value) if isinstance(value, str) else value
        except (TypeError, ValueError):
            _fail("provenance_invalid", column, "stored provenance JSON is invalid")
    return _validate_bundle(raw, verify_files=verify_files)


def rerun_input_params(bundle: Mapping[str, Any], gallery_dir: Path) -> dict[str, str]:
    """Translate verified recipe inputs to the existing queue upload/injection contract.

    CIV-E intentionally uses only queue parameters that are consumed by ``_process_pending``:
    subject image, pose image, and inpaint mask.  It refuses unknown or ambiguous inputs
    rather than passing inert metadata to ``submit_custom``.
    """
    manifests = {item["reference"]: item for item in bundle["input_hashes"]}
    aliases = {
        "image": "image", "subject": "image", "img2img": "image",
        "pose": "image_pose", "image_pose": "image_pose", "control_pose": "image_pose",
        "mask": "mask", "inpaint_mask": "mask",
    }
    params: dict[str, str] = {}
    for index, recipe_input in enumerate(bundle["recipe"].get("inputs", [])):
        reference = recipe_input["reference"]
        manifest = manifests[reference]
        kind = recipe_input["kind"].strip().lower()
        param = aliases.get(kind)
        if param is None:
            _fail("input_binding_unsupported", f"recipe.inputs[{index}].kind", "recipe input kind has no queue upload contract")
        if param in params:
            _fail("input_binding_ambiguous", f"recipe.inputs[{index}]", "multiple recipe inputs map to one queue input")
        try:
            relative = Path(manifest["local_path"]).resolve().relative_to(gallery_dir.resolve())
        except (OSError, ValueError):
            _fail("input_binding_path_invalid", f"input_hashes[{reference}].local_path", "required input must be inside gallery_dir")
        params[param] = relative.as_posix()

    workflow = bundle["workflow"]
    load_images = [node for node in workflow.values() if isinstance(node, Mapping) and node.get("class_type") == "LoadImage"]
    if "image" in params and not load_images:
        _fail("input_binding_missing", "workflow", "subject input requires a LoadImage node")
    if "image_pose" in params and (not load_images or ("image" in params and len(load_images) < 2)):
        _fail("input_binding_missing", "workflow", "pose input requires its own LoadImage node")
    if "mask" in params and not any(
        isinstance(node, Mapping) and node.get("class_type") == "LoadImageMask" for node in workflow.values()
    ):
        _fail("input_binding_missing", "workflow", "mask input requires a LoadImageMask node")
    return params


def persistable_bundle(bundle: Mapping[str, Any]) -> dict[str, str]:
    """Canonical DB column values, validated before the transaction is opened."""
    normalized = _validate_bundle(bundle)
    return {
        "recipe_json": canonical_json(normalized["recipe"]),
        "recipe_sha256": normalized["recipe_sha256"],
        "recipe_workflow_json": canonical_json(normalized["workflow"]),
        "recipe_workflow_sha256": normalized["workflow_sha256"],
        "recipe_input_hashes_json": canonical_json(normalized["input_hashes"]),
        "recipe_resource_locks_json": canonical_json(normalized["resource_locks"]),
        "recipe_runtime_provenance_json": canonical_json(normalized["runtime_provenance"]),
        "recipe_reproduction_level": normalized["reproduction_level"],
    }
