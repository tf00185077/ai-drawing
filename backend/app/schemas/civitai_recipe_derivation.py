"""Frozen CIV-V-B canonical GenerationRecipe derivation boundary."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SkipValidation, field_validator, model_validator

from app.schemas.generation_recipe import GenerationRecipe


CanonicalField = Literal[
    "base_prompt", "negative_prompt", "sampling.seed", "sampling.steps",
    "sampling.cfg", "sampling.sampler", "sampling.scheduler", "sampling.denoise",
    "sampling.width", "sampling.height",
]
DirectivePolicy = Literal["preserve", "replace", "randomize"]
CANONICAL_FIELDS: tuple[CanonicalField, ...] = (
    "base_prompt", "negative_prompt", "sampling.seed", "sampling.steps",
    "sampling.cfg", "sampling.sampler", "sampling.scheduler", "sampling.denoise",
    "sampling.width", "sampling.height",
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RecipeDerivationDirective(_StrictModel):
    field: CanonicalField
    policy: DirectivePolicy
    value: Any | None = None

    @model_validator(mode="after")
    def validate_policy_value_contract(self) -> "RecipeDerivationDirective":
        value_supplied = "value" in self.model_fields_set
        if self.policy == "preserve" and value_supplied:
            raise ValueError("preserve directives must not carry value")
        if self.policy == "replace" and not value_supplied:
            raise ValueError("replace directives require value")
        if self.policy == "randomize":
            if self.field != "sampling.seed":
                raise ValueError("randomize is only permitted for sampling.seed")
            if value_supplied:
                raise ValueError("randomize directives must not carry value")
        return self


class CivitaiRecipeDerivationRequest(_StrictModel):
    # Trusted parent models carry non-serializable provenance authority.  Revalidating
    # an existing instance would demote its confirmed evidence and change its hash.
    parent_recipe: SkipValidation[GenerationRecipe]
    parent_recipe_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    directives: list[RecipeDerivationDirective]

    @field_validator("parent_recipe", mode="before")
    @classmethod
    def validate_parent_recipe(cls, value: object) -> GenerationRecipe:
        return value if isinstance(value, GenerationRecipe) else GenerationRecipe.model_validate(value)

    @model_validator(mode="after")
    def validate_complete_unique_directives(self) -> "CivitaiRecipeDerivationRequest":
        fields = [directive.field for directive in self.directives]
        if len(fields) != len(CANONICAL_FIELDS) or set(fields) != set(CANONICAL_FIELDS):
            raise ValueError("directives must declare each canonical field exactly once")
        if len(set(fields)) != len(fields):
            raise ValueError("directives must declare each canonical field exactly once")
        return self


class AppliedDirective(_StrictModel):
    field: CanonicalField
    policy: DirectivePolicy
    parent_value: Any | None
    child_value: Any | None


class DerivationRequirements(_StrictModel):
    resolve_required: bool
    build_required: bool
    reason_codes: list[Literal["content_or_sampling_changed", "audited_workflow_invalidated"]] = Field(default_factory=list)


class CivitaiRecipeDerivationResponse(_StrictModel):
    child_recipe: GenerationRecipe
    parent_recipe_sha256: str
    child_recipe_sha256: str
    applied_directives: list[AppliedDirective]
    invalidated_evidence: dict[str, Any] = Field(default_factory=dict)
    requirements: DerivationRequirements
