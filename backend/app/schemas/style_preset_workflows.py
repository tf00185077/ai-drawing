"""Request and response models for saved style-preset workflows."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


KeywordInput = str | list[str]


class SaveStylePresetWorkflowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: int | str
    profile: str | None = None
    prompt_keywords: KeywordInput
    negative_prompt_keywords: KeywordInput = Field(default_factory=list)


class SaveStylePresetWorkflowResponse(BaseModel):
    preset_id: str
    profile: str | None = None
    source: dict[str, str]
    workflow_path: str
    prompt_keywords: list[str]
    negative_prompt_keywords: list[str]
    retest_required: bool = True


class TestStylePresetWorkflowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: str | None = None


class TestStylePresetWorkflowResponse(BaseModel):
    preset_id: str
    profile: str | None = None
    job_id: str
    status: str = "queued"
