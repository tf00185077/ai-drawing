"""Frozen CIV-V-G request/response schemas for durable variation sets."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.civitai_recipe_derivation import RecipeDerivationDirective
from app.schemas.civitai_recipe_variants import (
    CivitaiRecipeVariantInputBinding,
    CivitaiRecipeVariantGenerateRequest,
)
from app.schemas.civitai_source_aliases import CivitaiSourceAliasParentSelector
from app.schemas.civitai_recipes import RuntimeCapabilitiesPayload
from app.schemas.generation_recipe import GenerationRecipe, RuntimeProvenance


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CivitaiRecipeVariationSetChildSpec(_StrictModel):
    client_child_key: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    directives: list[RecipeDerivationDirective]


class CivitaiRecipeVariationSetCreateRequest(_StrictModel):
    """One caller-owned common Parent source; durable child identity stays backend-owned."""
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "allOf": [{"oneOf": [
                {"required": ["parent_recipe", "parent_recipe_sha256"], "not": {"required": ["source_alias"]}},
                {"required": ["source_alias"], "not": {"anyOf": [{"required": ["parent_recipe"]}, {"required": ["parent_recipe_sha256"]}]}},
            ]}],
        },
    )
    parent_recipe: GenerationRecipe | None = None
    parent_recipe_sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")
    source_alias: CivitaiSourceAliasParentSelector | None = None
    model_family: Literal["sdxl", "illustrious"]
    runtime_capabilities: RuntimeCapabilitiesPayload
    runtime_provenance: RuntimeProvenance
    input_bindings: dict[str, CivitaiRecipeVariantInputBinding] = Field(default_factory=dict)
    children: list[CivitaiRecipeVariationSetChildSpec] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_frozen_children(self) -> "CivitaiRecipeVariationSetCreateRequest":
        direct = self.parent_recipe is not None or self.parent_recipe_sha256 is not None
        alias = self.source_alias is not None
        if direct == alias or (direct and (self.parent_recipe is None or self.parent_recipe_sha256 is None)):
            raise ValueError("exactly one complete parent source is required")
        keys = [item.client_child_key for item in self.children]
        if len(keys) != len(set(keys)):
            raise ValueError("client_child_key must be unique within a variation set request")
        # Reuse the frozen V-F request boundary for each child before any durable set exists.
        for child in self.children:
            CivitaiRecipeVariantGenerateRequest(
                parent_recipe=self.parent_recipe,
                parent_recipe_sha256=self.parent_recipe_sha256,
                source_alias=self.source_alias,
                directives=child.directives,
                model_family=self.model_family,
                runtime_capabilities=self.runtime_capabilities,
                runtime_provenance=self.runtime_provenance,
                input_bindings=self.input_bindings,
            )
        return self


class CivitaiRecipeVariationSetIdResponse(_StrictModel):
    variation_set_id: str


class CivitaiRecipeVariationSetResponse(_StrictModel):
    variation_set_id: str
    parent_recipe_sha256: str
    members: list[dict]
    aggregate: dict
