"""Frozen CIV-V-F request, response, and lineage schemas."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.civitai_recipe_derivation import CivitaiRecipeDerivationRequest, RecipeDerivationDirective
from app.schemas.civitai_recipes import RuntimeCapabilitiesPayload
from app.schemas.generation_recipe import GenerationRecipe, RuntimeProvenance, canonical_runtime_lock_document


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CivitaiRecipeVariantInputBinding(_StrictModel):
    """A compiler input reference pinned to a verified local gallery file."""
    filename: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    local_path: str = Field(min_length=1)


class CivitaiRecipeVariantGenerateRequest(_StrictModel):
    """Only upstream inputs; all executable artifacts remain backend-owned."""
    parent_recipe: GenerationRecipe
    parent_recipe_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    directives: list[RecipeDerivationDirective]
    model_family: Literal["sdxl", "illustrious"]
    runtime_capabilities: RuntimeCapabilitiesPayload
    runtime_provenance: RuntimeProvenance
    input_bindings: dict[str, CivitaiRecipeVariantInputBinding] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_derivation_and_runtime_identity(self) -> "CivitaiRecipeVariantGenerateRequest":
        CivitaiRecipeDerivationRequest(
            parent_recipe=self.parent_recipe,
            parent_recipe_sha256=self.parent_recipe_sha256,
            directives=self.directives,
        )
        capabilities = self.runtime_capabilities.model_dump(mode="json")
        snapshot_document = {
            key: capabilities[key]
            for key in ("engine", "engine_version", "node_types", "sampler_names", "scheduler_names")
        }
        snapshot_digest = hashlib.sha256(
            json.dumps(snapshot_document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        if capabilities["snapshot_sha256"] != snapshot_digest:
            raise ValueError("runtime capability snapshot_sha256 must match canonical capabilities")
        if self.runtime_provenance.engine != self.runtime_capabilities.engine:
            raise ValueError("runtime provenance engine must match runtime capability snapshot")
        if self.runtime_provenance.engine_version != self.runtime_capabilities.engine_version:
            raise ValueError("runtime provenance engine_version must match runtime capability snapshot")
        if self.runtime_provenance.runtime_lock_sha256 is None:
            raise ValueError("runtime provenance runtime_lock_sha256 is required for variants")
        runtime_digest = hashlib.sha256(
            json.dumps(
                canonical_runtime_lock_document(self.runtime_provenance),
                ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if self.runtime_provenance.runtime_lock_sha256 != runtime_digest:
            raise ValueError("runtime provenance runtime_lock_sha256 must match canonical runtime lock")
        required_node_types = set(self.runtime_capabilities.node_types)
        runtime_node_types = set(self.runtime_provenance.node_versions)
        if runtime_node_types != required_node_types:
            raise ValueError("runtime provenance node_versions must exactly identify runtime capability node types")
        inspection = self.runtime_provenance.inspection_snapshot
        if not isinstance(inspection, dict):
            raise ValueError("runtime provenance inspection_snapshot must be an object")
        if inspection.get("snapshot_sha256") != capabilities["snapshot_sha256"]:
            raise ValueError("runtime provenance inspection snapshot must bind runtime capability snapshot_sha256")
        if inspection.get("engine") != self.runtime_capabilities.engine:
            raise ValueError("runtime provenance inspection engine must match runtime capability snapshot")
        if inspection.get("engine_version") != self.runtime_capabilities.engine_version:
            raise ValueError("runtime provenance inspection engine_version must match runtime capability snapshot")
        inspected_node_types = inspection.get("node_types")
        if not isinstance(inspected_node_types, list) or set(inspected_node_types) != required_node_types or len(inspected_node_types) != len(required_node_types):
            raise ValueError("runtime provenance inspection node_types must exactly match runtime capability snapshot")
        return self


class CivitaiRecipeVariantLineage(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    variant_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    parent_recipe_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    derived_recipe_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    built_child_recipe_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    applied_directives: list[dict[str, Any]]
    invalidated_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    strict_resolution_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    compatibility_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    workflow_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    resource_lock_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    lineage_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CivitaiRecipeVariantGenerateResponse(_StrictModel):
    variant_id: str
    parent_recipe_sha256: str
    derived_recipe_sha256: str
    built_child_recipe_sha256: str
    workflow_sha256: str
    resource_lock_sha256: str
    job_id: str
    status: Literal["queued"]
    derivation: dict[str, Any]
    compatibility: dict[str, Any]
