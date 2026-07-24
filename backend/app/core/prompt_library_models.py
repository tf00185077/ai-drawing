"""Strict, versioned models for persisted Prompt Library JSON documents."""

from __future__ import annotations

import unicodedata
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator


SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
Polarity = Literal["positive", "negative"]
ResourceType = Literal["category", "entry", "combination"]
Slug = Annotated[str, Field(pattern=SLUG_PATTERN)]


def validate_combination_id(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("combination id must be a string")
    normalized = unicodedata.normalize("NFC", value)
    if not 1 <= len(normalized) <= 128:
        raise ValueError("combination id must contain 1 to 128 characters")
    parts = normalized.split("-")
    if any(not part for part in parts):
        raise ValueError("combination id cannot start/end with or repeat hyphens")
    if any(
        not all(unicodedata.category(char)[0] in {"L", "N"} for char in part)
        for part in parts
    ):
        raise ValueError(
            "combination id may contain only Unicode letters, numbers, and hyphens"
        )
    return normalized


CombinationId = Annotated[str, BeforeValidator(validate_combination_id)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PromptLibraryManifest(StrictModel):
    schema_version: Literal[1] = 1
    library_id: Slug
    name: str = Field(min_length=1)
    description_zh: str = Field(min_length=1)


class PromptEntry(StrictModel):
    id: Slug
    name_zh: str = Field(min_length=1)
    description_zh: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    order: int = Field(default=10, ge=0)
    revision: int = Field(default=1, ge=1)
    archived: bool = False


class PromptCategory(StrictModel):
    schema_version: Literal[1] = 1
    id: Slug
    polarity: Polarity
    name_zh: str = Field(min_length=1)
    description_zh: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    order: int = Field(default=10, ge=0)
    revision: int = Field(default=1, ge=1)
    archived: bool = False
    entries: list[PromptEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_entry_ids(self) -> "PromptCategory":
        entry_ids = [entry.id for entry in self.entries]
        if len(entry_ids) != len(set(entry_ids)):
            raise ValueError("duplicate entry id")
        return self


class PromptEntryRef(StrictModel):
    polarity: Polarity
    category_id: Slug
    entry_id: Slug


class PromptFragment(StrictModel):
    kind: Literal["entry", "literal"]
    ref: PromptEntryRef | None = None
    snapshot: str
    source_revision: int | None = None
    weight: float = Field(default=1.0, gt=0.0, le=2.0)
    order: int = Field(default=10, ge=0)

    @model_validator(mode="after")
    def validate_kind(self) -> "PromptFragment":
        if self.kind == "entry" and self.ref is None:
            raise ValueError("entry fragment requires ref")
        if self.kind == "literal" and self.ref is not None:
            raise ValueError("literal fragment cannot have ref")
        if self.kind == "literal" and self.source_revision is not None:
            raise ValueError("literal fragment cannot have source_revision")
        if not self.snapshot.strip():
            raise ValueError("fragment snapshot cannot be empty")
        return self


class PromptCombination(StrictModel):
    schema_version: Literal[1] = 1
    id: CombinationId
    name_zh: str = Field(min_length=1)
    description_zh: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    order: int = Field(default=10, ge=0)
    revision: int = Field(default=1, ge=1)
    archived: bool = False
    legacy_template: bool = False
    positive: list[PromptFragment] = Field(default_factory=list)
    negative: list[PromptFragment] = Field(default_factory=list)
    positive_prompt_snapshot: str = ""
    negative_prompt_snapshot: str = ""
