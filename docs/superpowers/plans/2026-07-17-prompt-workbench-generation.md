# Prompt Workbench and Workflow Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the old `/generate` form with a unified Prompt Workbench that browses, edits, composes, copies, and saves positive/negative prompts, then optionally sends them through an eligible text-to-image workflow with descriptor-driven overrides and explicit seed behavior.

**Architecture:** Extend the workflow catalog with generation-form descriptors derived from validated manifests, workflow JSON, installed resources, and best-effort live ComfyUI sampler capabilities. Preserve legacy generation defaults unless `use_workflow_defaults=true`; the new React feature consumes only typed Prompt Library and generation APIs, keeps builder state independent from workflow state, and treats backend composition as the prompt-string authority.

**Tech Stack:** Python 3.11, FastAPI, Pydantic 2, ComfyUI REST/WebSocket integration, React 18, TypeScript 5, Vite 5, Tailwind CSS, Vitest, React Testing Library.

---

## Plan-set position and prerequisite

This is plan 2 of 3. Complete `2026-07-17-prompt-library-service.md` first. Complete this plan before the agent-parity changes in `2026-07-17-prompt-library-agent-tools.md`.

## Locked file structure

### Backend create

- `backend/app/core/workflow_form.py` — pure workflow eligibility/introspection plus live/fallback option enrichment.
- `backend/tests/test_workflow_generation_form.py` — pure descriptor and API tests.

### Backend modify

- `backend/app/schemas/generate.py:18-54` — optional overrides, `use_workflow_defaults`, and `seed_mode` validation.
- `backend/app/api/generate.py:37-125` — omit absent override keys and forward the new controls.
- `backend/app/core/queue.py:64-91,311-465,560-580` — resolve legacy/default-preserving seed and parameter behavior and record actual values.
- `backend/app/core/workflow.py:38-296` — expose actual sampler settings after injection.
- `backend/app/api/workflow_catalog.py:45-102` — add `GET /api/workflow-catalog/generation-forms`.
- `backend/tests/test_generate_api.py`
- `backend/tests/test_queue.py`
- `backend/tests/test_workflow.py`

### Frontend create

```text
frontend/src/features/promptLibrary/
├── types.ts
├── api.ts
├── api.test.ts
├── compositionState.ts
├── compositionState.test.ts
├── usePromptLibrary.ts
├── usePromptLibrary.test.tsx
├── PromptWorkbench.tsx
├── PromptWorkbench.test.tsx
├── LibrarySidebar.tsx
├── EntryBrowser.tsx
├── CompositionBoard.tsx
├── CombinationPicker.tsx
├── EntryEditorModal.tsx
├── CategoryEditorModal.tsx
├── CombinationEditorModal.tsx
├── GenerationPanel.tsx
└── GenerationPanel.test.tsx
```

### Frontend modify

- `frontend/package.json` — add a TypeScript-only check command.
- `frontend/src/types/api.ts:6-34` — align generation and workflow descriptor contracts with backend.
- `frontend/src/pages/Generate.tsx` — thin page wrapper around `PromptWorkbench`.
- `frontend/src/App.tsx:14-27` — keep `/generate`, rename its label.
- `frontend/src/pages/Dashboard.tsx` — update the generation card copy.
- `frontend/src/App.test.tsx` — route smoke coverage.
- `docs/PROGRESS.md` — record the completed human-facing stage and its verification.

## Cross-layer contracts

The full generation request used by backend, frontend, and later MCP is:

```typescript
export interface GenerateRequest {
  checkpoint?: string;
  lora?: string;
  loras?: Array<{ name: string; strength_model: number; strength_clip?: number }>;
  template?: string;
  diffusion_model?: string;
  text_encoder?: string;
  vae?: string;
  prompt: string;
  negative_prompt?: string;
  use_workflow_defaults?: boolean;
  seed_mode?: "workflow_default" | "random" | "fixed";
  seed?: number;
  steps?: number;
  cfg?: number;
  width?: number;
  height?: number;
  batch_size?: number;
  sampler_name?: string;
  scheduler?: string;
  lora_strength?: number;
  denoise?: number;
}
```

Rules:

- Builder-only copy/save works with no workflow selected.
- Saved combinations never include workflow or generation fields.
- The workbench lists only valid, non-deprecated, text-only `txt2img` workflows.
- The UI defaults to `use_workflow_defaults=true`, sends no empty override, and always displays seed mode.
- `seed_mode=fixed` requires `seed`; `random` and `workflow_default` reject `seed`.
- `workflow_default` requires `use_workflow_defaults=true`.
- Legacy callers that omit both new fields retain current behavior: steps 20, CFG 7, and random seed unless an explicit seed was supplied.

---

### Task 1: Workflow generation-form descriptors

**Files:**

- Create: `backend/app/core/workflow_form.py`
- Modify: `backend/app/api/workflow_catalog.py:45-102`
- Test: `backend/tests/test_workflow_generation_form.py`

- [ ] **Step 1: Write failing eligibility and descriptor tests**

Create workflow fixtures with conspicuous defaults and manifest fixtures for valid txt2img, image-input, deprecated, invalid, and video cases:

```python
def test_generation_forms_include_only_pure_text_to_image(tmp_path: Path) -> None:
    write_workflow(tmp_path, "plain", txt2img_workflow())
    write_manifest(tmp_path, "plain", modality="txt2img", io=["text"])
    write_workflow(tmp_path, "pose", txt2img_workflow())
    write_manifest(tmp_path, "pose", modality="txt2img", io=["text", "pose_ref"], conditioning=["controlnet_pose"])
    write_workflow(tmp_path, "video", txt2img_workflow())
    write_manifest(tmp_path, "video", modality="txt2video", io=["text"])

    result = build_generation_forms(tmp_path, resources=empty_resources(), object_info={})

    assert [item.id for item in result.items] == ["plain"]


def test_descriptor_reports_supported_fields_defaults_and_options(tmp_path: Path) -> None:
    workflow = txt2img_workflow(
        checkpoint="workflow.ckpt",
        seed=2468,
        steps=31,
        cfg=5.5,
        sampler="euler",
        scheduler="normal",
        width=768,
        height=1152,
        batch_size=2,
    )
    write_workflow(tmp_path, "plain", workflow)
    write_manifest(tmp_path, "plain", modality="txt2img", io=["text"])

    result = build_generation_forms(
        tmp_path,
        resources=resources(checkpoints=["installed.ckpt"]),
        object_info=ksampler_object_info(samplers=["euler", "dpmpp_2m"], schedulers=["normal", "karras"]),
    )

    form = result.items[0]
    assert descriptor(form, "checkpoint").default == "workflow.ckpt"
    assert descriptor(form, "checkpoint").options == ["installed.ckpt"]
    assert descriptor(form, "steps").default == 31
    assert descriptor(form, "seed").default == 2468
    assert descriptor(form, "sampler_name").options == ["euler", "dpmpp_2m"]
    assert descriptor(form, "scheduler").options == ["normal", "karras"]
    assert result.capability_source == "live"
```

Add an API test that patches ComfyUI failure and still receives `200`, workflow-derived defaults, installed model options, and `capability_source="fallback"`.

- [ ] **Step 2: Run the descriptor tests and confirm failure**

Run:

```powershell
python -m pytest backend/tests/test_workflow_generation_form.py -q
```

Expected: collection fails because `app.core.workflow_form` is absent and the route returns 404.

- [ ] **Step 3: Implement eligibility and graph introspection**

Define these models in `workflow_form.py`:

```python
ParameterKind = Literal["number", "select", "lora_list", "seed"]


class WorkflowParameterDescriptor(BaseModel):
    name: str
    kind: ParameterKind
    default: Any | None = None
    defaults: list[Any] = Field(default_factory=list)
    options: list[str] = Field(default_factory=list)
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    slot_count: int | None = None


class WorkflowGenerationForm(BaseModel):
    id: str
    display_name: str
    description: str
    model_family: str
    modality: Literal["txt2img"] = "txt2img"
    io: list[str]
    fields: list[WorkflowParameterDescriptor]


class GenerationFormsResponse(BaseModel):
    items: list[WorkflowGenerationForm]
    capability_source: Literal["live", "fallback"]
```

Eligibility is:

```python
EXTERNAL_IO = {"image_ref", "pose_ref", "mask", "first_frame", "last_frame", "video_ref", "audio_ref"}
EXTERNAL_CONDITIONING = {"controlnet_pose", "pose_transfer"}


def eligible(manifest: WorkflowManifest, valid: bool) -> bool:
    return (
        valid
        and not manifest.deprecated
        and manifest.modality == "txt2img"
        and "text" in manifest.io
        and not (set(manifest.io) & EXTERNAL_IO)
        and not (set(manifest.conditioning) & EXTERNAL_CONDITIONING)
    )
```

Detect fields through node types already supported by `apply_params`: `CheckpointLoaderSimple`, `LoraLoader`, `LoraLoaderModelOnly`, `UNETLoader`, `CLIPLoader`, `VAELoader`, `KSampler`, `EmptyLatentImage`, and `EmptySD3LatentImage`. Preserve unique defaults in workflow order; when all matching nodes agree, set `default`, otherwise leave `default=None` and expose all values in `defaults`. A LoRA descriptor uses `name="loras"`, `kind="lora_list"`, `slot_count` equal to loader count, and default objects with `name`, `strength_model`, and optional `strength_clip`.

- [ ] **Step 4: Add best-effort live sampler enrichment and the route**

At the API layer, gather installed checkpoint, LoRA, diffusion-model, text-encoder, and VAE options with existing `app.core.resources` functions. Call `object_info = ComfyUIClient().get_object_info()` and `extract_node_schema(object_info, "KSampler")`; map combo options for `sampler_name` and `scheduler`. Catch ComfyUI/httpx failures, leave those options at their workflow-derived values, and return `capability_source="fallback"`.

Add:

```python
@router.get("/generation-forms", response_model=GenerationFormsResponse)
async def generation_forms():
    return build_generation_forms_with_runtime_options()
```

Define this static route before any future `/{workflow_id}` route.

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
python -m pytest backend/tests/test_workflow_generation_form.py backend/tests/test_workflow_manifest.py backend/tests/test_comfyui_nodes.py -q
```

Expected: all selected tests pass.

Commit:

```powershell
git add backend/app/core/workflow_form.py backend/app/api/workflow_catalog.py backend/tests/test_workflow_generation_form.py
git commit -m "feat: describe workflow generation forms"
```

### Task 2: Workflow-default generation and explicit seed modes

**Files:**

- Modify: `backend/app/schemas/generate.py:18-54`
- Modify: `backend/app/api/generate.py:37-125`
- Modify: `backend/app/core/queue.py:64-91,311-465,560-580`
- Modify: `backend/app/core/workflow.py:38-296`
- Modify: `backend/tests/test_generate_api.py`
- Modify: `backend/tests/test_queue.py`
- Modify: `backend/tests/test_workflow.py`

- [ ] **Step 1: Write failing request-validation and API-forwarding tests**

Append:

```python
@pytest.mark.parametrize(
    ("payload", "error"),
    [
        ({"prompt": "x", "use_workflow_defaults": True}, "invalid_seed_mode"),
        ({"prompt": "x", "use_workflow_defaults": True, "seed_mode": "fixed"}, "invalid_seed_mode"),
        ({"prompt": "x", "use_workflow_defaults": True, "seed_mode": "random", "seed": 4}, "invalid_seed_mode"),
        ({"prompt": "x", "seed_mode": "workflow_default"}, "invalid_seed_mode"),
    ],
)
def test_generate_rejects_inconsistent_seed_controls(client, payload, error) -> None:
    response = client.post("/api/generate/", json=payload)
    assert response.status_code == 422
    assert error in response.text


def test_generate_forwards_only_explicit_workflow_overrides(client) -> None:
    with patch("app.api.generate.submit", return_value="job") as submit:
        response = client.post(
            "/api/generate/",
            json={
                "template": "default",
                "prompt": "dress",
                "negative_prompt": "",
                "use_workflow_defaults": True,
                "seed_mode": "random",
            },
        )
    assert response.status_code == 201
    params = submit.call_args.args[0]
    assert params == {
        "template": "default",
        "prompt": "dress",
        "negative_prompt": "",
        "use_workflow_defaults": True,
        "seed_mode": "random",
    }
```

- [ ] **Step 2: Write failing queue behavior tests**

Patch `load_template` with a workflow whose checkpoint, sampler settings, seed, and dimensions differ from API defaults. Assert:

```python
def test_workflow_default_mode_preserves_baked_values(queue_harness) -> None:
    queue_harness.submit({
        "template": "plain",
        "prompt": "dress",
        "negative_prompt": "",
        "use_workflow_defaults": True,
        "seed_mode": "workflow_default",
    })
    sent = queue_harness.submitted_workflow()
    assert sampler(sent)["seed"] == 2468
    assert sampler(sent)["steps"] == 31
    assert sampler(sent)["cfg"] == 5.5
    assert checkpoint(sent) == "workflow.ckpt"
    assert latent(sent)["width"] == 768
    assert latent(sent)["height"] == 1152


def test_workflow_default_random_seed_changes_only_seed(queue_harness, monkeypatch) -> None:
    monkeypatch.setattr("app.core.queue.random.randint", lambda _a, _b: 987654)
    queue_harness.submit({
        "template": "plain",
        "prompt": "dress",
        "use_workflow_defaults": True,
        "seed_mode": "random",
    })
    sent = queue_harness.submitted_workflow()
    assert sampler(sent)["seed"] == 987654
    assert sampler(sent)["steps"] == 31
    assert sampler(sent)["cfg"] == 5.5


def test_legacy_request_keeps_20_7_and_random_seed(queue_harness, monkeypatch) -> None:
    monkeypatch.setattr("app.core.queue.random.randint", lambda _a, _b: 123456)
    queue_harness.submit({"template": "plain", "prompt": "dress"})
    sent = queue_harness.submitted_workflow()
    assert sampler(sent)["seed"] == 123456
    assert sampler(sent)["steps"] == 20
    assert sampler(sent)["cfg"] == 7.0
```

Add a recording assertion that `job.params` contains the actual baked/random/fixed seed, steps, and CFG after `apply_params`.

- [ ] **Step 3: Run the focused backend tests and confirm failure**

Run:

```powershell
python -m pytest backend/tests/test_generate_api.py backend/tests/test_queue.py backend/tests/test_workflow.py -q
```

Expected: the new 422 tests, omitted-key assertion, and workflow-default queue tests fail.

- [ ] **Step 4: Implement schema, API, queue, and recording behavior**

In `GenerateRequest`, change `steps` and `cfg` defaults to `None`, add `use_workflow_defaults: bool = False`, and add:

```python
SeedMode = Literal["workflow_default", "random", "fixed"]

@model_validator(mode="after")
def validate_seed_controls(self) -> "GenerateRequest":
    if self.seed_mode is None:
        if self.use_workflow_defaults:
            raise PydanticCustomError("invalid_seed_mode", "seed_mode is required when use_workflow_defaults is true")
        return self
    if self.seed_mode == "workflow_default" and not self.use_workflow_defaults:
        raise PydanticCustomError("invalid_seed_mode", "workflow_default seed requires workflow defaults")
    if self.seed_mode == "fixed" and self.seed is None:
        raise PydanticCustomError("invalid_seed_mode", "fixed seed mode requires seed")
    if self.seed_mode != "fixed" and self.seed is not None:
        raise PydanticCustomError("invalid_seed_mode", "seed is only accepted in fixed mode")
    return self
```

Build API params by starting with `prompt`, then add every optional key only when it is not `None`; include `negative_prompt` even when it is the empty string. Always add `use_workflow_defaults` when true and `seed_mode` when present.

In the queue, infer legacy seed mode as `fixed` when a seed exists and `random` otherwise. When `use_workflow_defaults` is true: do not inject `default_checkpoint`, do not apply the SDXL 1024 heuristic, leave steps/CFG `None`, and map modes to baked `None`, generated random, or fixed seed. When false: retain default checkpoint, SDXL heuristic, steps 20, CFG 7, and legacy seed behavior.

Add to `workflow.py`:

```python
def get_sampling_params_from_workflow(workflow: Mapping[str, Any]) -> dict[str, Any]:
    for node in workflow.values():
        if isinstance(node, dict) and node.get("class_type") == "KSampler":
            inputs = node.get("inputs", {})
            return {
                key: inputs.get(key)
                for key in ("seed", "steps", "cfg", "sampler_name", "scheduler", "denoise")
                if inputs.get(key) is not None
            }
    return {}
```

After `apply_params`, set missing `job.params` sampling values from this function so `recording.save()` stores actual workflow defaults.

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
python -m pytest backend/tests/test_generate_api.py backend/tests/test_queue.py backend/tests/test_workflow.py -q
```

Expected: all selected tests pass and existing legacy generation assertions remain green.

Commit:

```powershell
git add backend/app/schemas/generate.py backend/app/api/generate.py backend/app/core/queue.py backend/app/core/workflow.py backend/tests/test_generate_api.py backend/tests/test_queue.py backend/tests/test_workflow.py
git commit -m "feat: preserve workflow defaults during generation"
```

### Task 3: Frontend contracts, API client, and composition reducer

**Files:**

- Create: `frontend/src/features/promptLibrary/types.ts`
- Create: `frontend/src/features/promptLibrary/api.ts`
- Create: `frontend/src/features/promptLibrary/api.test.ts`
- Create: `frontend/src/features/promptLibrary/compositionState.ts`
- Create: `frontend/src/features/promptLibrary/compositionState.test.ts`
- Modify: `frontend/src/types/api.ts:6-34`
- Modify: `frontend/package.json`

- [ ] **Step 1: Write failing API-client tests**

Use `vi.stubGlobal("fetch", vi.fn())`. Verify query encoding, compose bodies, optimistic tokens, and FastAPI error normalization:

```typescript
it("encodes fuzzy-search filters", async () => {
  mockJson({ results: [], total: 0, diagnostics: [] });
  await promptLibraryApi.search({
    q: "洋裝 dress",
    polarity: "positive",
    category_id: "clothing",
    resource_types: ["entry", "combination"],
    threshold: 45,
    limit: 50,
  });
  expect(fetch).toHaveBeenCalledWith(
    "/api/prompt-library/search?q=%E6%B4%8B%E8%A3%9D+dress&polarity=positive&category_id=clothing&resource_types=entry&resource_types=combination&threshold=45&limit=50",
    expect.objectContaining({ signal: undefined }),
  );
});

it("normalizes a revision conflict", async () => {
  mockJson(
    { detail: { code: "revision_conflict", message: "stale", hint: "reload", details: {} } },
    409,
  );
  await expect(promptLibraryApi.saveEntry("positive", "clothing", "dress", entryWrite())).rejects.toMatchObject({
    name: "ApiError",
    status: 409,
    code: "revision_conflict",
    message: "stale",
    hint: "reload",
  });
});
```

- [ ] **Step 2: Write failing reducer tests**

```typescript
it("keeps positive and negative selections symmetric and ordered", () => {
  let state = emptyComposition();
  state = compositionReducer(state, { type: "addEntry", polarity: "positive", entry: dressEntry });
  state = compositionReducer(state, { type: "addLiteral", polarity: "negative", text: "low quality" });
  state = compositionReducer(state, { type: "setWeight", polarity: "positive", clientId: state.positive[0].client_id, weight: 1.2 });
  expect(buildComposeRequest(state)).toEqual({
    positive: [expect.objectContaining({ kind: "entry", weight: 1.2, order: 10 })],
    negative: [expect.objectContaining({ kind: "literal", snapshot: "low quality", order: 10 })],
  });
});

it("does not add the same reference twice", () => {
  const once = compositionReducer(emptyComposition(), { type: "addEntry", polarity: "positive", entry: dressEntry });
  const twice = compositionReducer(once, { type: "addEntry", polarity: "positive", entry: dressEntry });
  expect(twice.positive).toHaveLength(1);
});

it("loads a combination without carrying generation state", () => {
  const loaded = compositionReducer(emptyComposition(), { type: "loadCombination", combination });
  expect(loaded.positive).toHaveLength(combination.positive.length);
  expect(Object.keys(loaded)).toEqual(["positive", "negative"]);
});
```

- [ ] **Step 3: Run both test files and confirm failure**

Run from `frontend/`:

```powershell
npm test -- src/features/promptLibrary/api.test.ts src/features/promptLibrary/compositionState.test.ts
```

Expected: test collection fails because the feature modules do not exist.

- [ ] **Step 4: Implement exact types, client methods, and reducer actions**

`types.ts` defines `PromptPolarity`, `PromptResourceType`, manifest, diagnostic, category summary/detail, entry/ref/fragment, combination, search hit/response, compose request/response, archive request, version token, and `WorkbenchSelection extends PromptFragment` with `client_id`.

`api.ts` exports `ApiError` and `promptLibraryApi` with:

```typescript
catalog(signal?: AbortSignal)
category(polarity, categoryId, signal?: AbortSignal)
search(params, signal?: AbortSignal)
compose(body, signal?: AbortSignal)
saveCategory(polarity, categoryId, body)
saveEntry(polarity, categoryId, entryId, body)
archive(body)
combinations(signal?: AbortSignal)
combination(combinationId, signal?: AbortSignal)
saveCombination(combinationId, body)
generationForms(signal?: AbortSignal)
generate(body)
queue(signal?: AbortSignal)
```

Encode list query params as repeated keys. Parse a failed response's `detail` whether it is a string or `{code,message,hint,details}`; default hint is `Reload the resource and retry.` for 409 and `Check the submitted fields.` for 422.

`compositionState.ts` exports `emptyComposition`, `compositionReducer`, `normalizeOrder`, and `buildComposeRequest`. Supported actions are `addEntry`, `addLiteral`, `remove`, `move`, `dropAt`, `setWeight`, `loadCombination`, and `clear`. Normalize each polarity independently to orders beginning `10, 20, 30` and continuing in increments of 10; strip `client_id` before API serialization. Entry refs are unique per polarity; literals remain distinct.

Update `src/types/api.ts` to the full `GenerateRequest` contract above plus `WorkflowParameterDescriptor`, `WorkflowGenerationForm`, and `GenerationFormsResponse`. Add `"typecheck": "tsc --noEmit"` to package scripts.

- [ ] **Step 5: Run tests, typecheck, and commit**

```powershell
npm test -- src/features/promptLibrary/api.test.ts src/features/promptLibrary/compositionState.test.ts
npm run typecheck
```

Expected: both commands exit 0.

Commit from repository root:

```powershell
git add frontend/package.json frontend/src/types/api.ts frontend/src/features/promptLibrary/types.ts frontend/src/features/promptLibrary/api.ts frontend/src/features/promptLibrary/api.test.ts frontend/src/features/promptLibrary/compositionState.ts frontend/src/features/promptLibrary/compositionState.test.ts
git commit -m "feat: add prompt workbench client state"
```

### Task 4: Library hook, browsing, fuzzy search, and CRUD editors

**Files:**

- Create: `frontend/src/features/promptLibrary/usePromptLibrary.ts`
- Create: `frontend/src/features/promptLibrary/usePromptLibrary.test.tsx`
- Create: `frontend/src/features/promptLibrary/LibrarySidebar.tsx`
- Create: `frontend/src/features/promptLibrary/EntryBrowser.tsx`
- Create: `frontend/src/features/promptLibrary/EntryEditorModal.tsx`
- Create: `frontend/src/features/promptLibrary/CategoryEditorModal.tsx`

- [ ] **Step 1: Write failing hook tests for load, debounce, cancellation, and invalidation**

Use fake timers and mock the feature API module:

```typescript
it("debounces search by 250ms and aborts the older request", async () => {
  vi.useFakeTimers();
  const { result, rerender } = renderHook(({ query }) => usePromptLibrary({ query, polarity: "positive", categoryId: "clothing" }), {
    initialProps: { query: "dre" },
  });
  rerender({ query: "dress" });
  await vi.advanceTimersByTimeAsync(249);
  expect(promptLibraryApi.search).not.toHaveBeenCalled();
  await vi.advanceTimersByTimeAsync(1);
  expect(promptLibraryApi.search).toHaveBeenCalledTimes(1);
  expect(promptLibraryApi.search).toHaveBeenCalledWith(
    expect.objectContaining({ q: "dress", polarity: "positive", category_id: "clothing" }),
    expect.any(AbortSignal),
  );
  expect(result.current.searching).toBe(true);
});

it("reloads catalog category combinations and composition after a mutation", async () => {
  const { result } = renderHook(() => usePromptLibrary({ query: "", polarity: "positive", categoryId: "clothing" }));
  await act(() => result.current.saveEntry("positive", "clothing", "dress", entryWrite));
  expect(promptLibraryApi.catalog).toHaveBeenCalledTimes(2);
  expect(promptLibraryApi.category).toHaveBeenCalledTimes(2);
  expect(promptLibraryApi.combinations).toHaveBeenCalledTimes(2);
});
```

- [ ] **Step 2: Write failing browsing/editor component tests**

Render with explicit props rather than a real backend. Assert positive/negative tabs, category selection, description/prompt display, multi-add buttons, free-text dual actions, labeled dialog fields, revision/etag forwarding, archive confirmation, and 409 hint rendering.

```typescript
it("offers free text as a literal or a new library entry", () => {
  render(<EntryBrowser query="cerulean coat" entries={[]} onAddLiteral={addLiteral} onCreateEntry={createEntry} />);
  fireEvent.click(screen.getByRole("button", { name: "加入組合" }));
  fireEvent.click(screen.getByRole("button", { name: "新增至資料庫" }));
  expect(addLiteral).toHaveBeenCalledWith("cerulean coat");
  expect(createEntry).toHaveBeenCalledWith(expect.objectContaining({ prompt: "cerulean coat" }));
});

it("uses a category fuzzy hit as navigation instead of a prompt fragment", () => {
  render(<EntryBrowser query="服裝提示" hits={[clothingCategoryHit]} onOpenCategory={openCategory} onAddEntry={addEntry} />);
  fireEvent.click(screen.getByRole("button", { name: "開啟分類 服裝" }));
  expect(openCategory).toHaveBeenCalledWith("positive", "clothing");
  expect(addEntry).not.toHaveBeenCalled();
});

it("shows an actionable conflict without overwriting", async () => {
  saveEntry.mockRejectedValue(new ApiError(409, "revision_conflict", "內容已變更", "重新載入後再試", {}));
  render(<EntryEditorModal {...editorProps} />);
  fireEvent.click(screen.getByRole("button", { name: "儲存" }));
  expect(await screen.findByText("重新載入後再試")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "重新載入" })).toBeInTheDocument();
});
```

- [ ] **Step 3: Run hook and UI tests and confirm failure**

```powershell
npm test -- src/features/promptLibrary/usePromptLibrary.test.tsx src/features/promptLibrary/PromptWorkbench.test.tsx
```

Expected: collection fails because the hook/components are absent.

- [ ] **Step 4: Implement the hook and browse/edit components**

`usePromptLibrary` loads catalog and combinations once, loads the active category on change, uses a 250ms timeout only for non-empty fuzzy queries, aborts the prior search, ignores `AbortError`, and exposes `reloadAll`, mutation methods, diagnostics, `searching`, and `error`. Empty search displays the active category's ordered entries without calling `/search`. The main search requests category and entry resources; category hits navigate to that category and entry hits can be added. `CombinationPicker` runs the same backend fuzzy search with `resource_types=["combination"]`, so names, descriptions, prompt snapshots, aliases, and keywords are searchable without a second client-side algorithm.

`LibrarySidebar` has Positive/Negative tabs, two-level category navigation, combination access, and a non-blocking diagnostics panel. `EntryBrowser` shows Chinese name and explanation, English prompt, matched fields, and an Add button on every entry; category hits instead show an Open Category action. Selecting categories never clears composition. `EntryEditorModal` and `CategoryEditorModal` use `role="dialog"`, `aria-modal="true"`, labels for every field, comma-split trimmed aliases/keywords, exact expected revision/etag tokens, archive confirmation, and an explicit reload action after 409; neither silently retries a write.

- [ ] **Step 5: Run tests and commit**

```powershell
npm test -- src/features/promptLibrary/usePromptLibrary.test.tsx src/features/promptLibrary/PromptWorkbench.test.tsx
npm run typecheck
```

Expected: all selected tests and typecheck pass.

Commit:

```powershell
git add frontend/src/features/promptLibrary/usePromptLibrary.ts frontend/src/features/promptLibrary/usePromptLibrary.test.tsx frontend/src/features/promptLibrary/LibrarySidebar.tsx frontend/src/features/promptLibrary/EntryBrowser.tsx frontend/src/features/promptLibrary/EntryEditorModal.tsx frontend/src/features/promptLibrary/CategoryEditorModal.tsx frontend/src/features/promptLibrary/PromptWorkbench.test.tsx
git commit -m "feat: browse and edit prompt library"
```

### Task 5: Composition board and saved combinations

**Files:**

- Create: `frontend/src/features/promptLibrary/CompositionBoard.tsx`
- Create: `frontend/src/features/promptLibrary/CombinationPicker.tsx`
- Create: `frontend/src/features/promptLibrary/CombinationEditorModal.tsx`
- Modify: `frontend/src/features/promptLibrary/PromptWorkbench.test.tsx`

- [ ] **Step 1: Add failing composition and saved-combination tests**

Mock `navigator.clipboard.writeText` and assert both lanes have identical controls:

```typescript
it("reorders, weights, and copies server-composed prompts", async () => {
  render(<CompositionBoard {...boardProps} />);
  fireEvent.change(screen.getByLabelText("dress 權重"), { target: { value: "1.2" } });
  fireEvent.click(screen.getByRole("button", { name: "dress 上移" }));
  fireEvent.click(screen.getByRole("button", { name: "複製 Positive Prompt" }));
  expect(boardProps.onSetWeight).toHaveBeenCalledWith("positive", "dress-client", 1.2);
  expect(boardProps.onMove).toHaveBeenCalledWith("positive", "dress-client", -1);
  expect(navigator.clipboard.writeText).toHaveBeenCalledWith("(dress:1.2), 1girl");
});

it("loads a saved combination without changing generation controls", () => {
  render(<PromptWorkbench />);
  fireEvent.change(screen.getByLabelText("Workflow"), { target: { value: "default" } });
  fireEvent.change(screen.getByLabelText("Seed 模式"), { target: { value: "random" } });
  fireEvent.click(screen.getByRole("button", { name: "載入 我的洋裝" }));
  expect(screen.getByLabelText("Workflow")).toHaveValue("default");
  expect(screen.getByLabelText("Seed 模式")).toHaveValue("random");
  expect(screen.getByText("dress")).toBeInTheDocument();
});
```

Test new save with revision 0/no etag, update with current revision+etag, archive, repaired-fragment loading, and warning display.

- [ ] **Step 2: Run the integration test and confirm failure**

```powershell
npm test -- src/features/promptLibrary/PromptWorkbench.test.tsx
```

Expected: tests fail because composition and combination components are absent.

- [ ] **Step 3: Implement the two-lane composition board**

Always render Positive and Negative lanes. Each item supports remove, numeric weight `(0, 2]`, up/down buttons, and native drag/drop; retain buttons for keyboard access. Add a free-text input per lane. Send state through `/compose` after changes and display only `ComposeResponse.positive_prompt` and `.negative_prompt`; do not reproduce the weight formatter in TypeScript. Render `missing_reference`, `archived_reference`, `duplicate_reference`, and repair warnings. Copy each server output independently.

- [ ] **Step 4: Implement combination list/editor semantics**

`CombinationPicker` supports list, fuzzy search, load, edit, and archive. `CombinationEditorModal` edits id/name/description/aliases/keywords and saves only metadata plus current positive/negative fragments. New saves send `expected_revision: 0` without an etag; updates send both current values. On load, use server-repaired fragments and prompt snapshots. After an entry update, reload combinations and recompose; do not patch snapshots in the browser.

- [ ] **Step 5: Run tests and commit**

```powershell
npm test -- src/features/promptLibrary/compositionState.test.ts src/features/promptLibrary/PromptWorkbench.test.tsx
npm run typecheck
```

Expected: all selected tests and typecheck pass.

Commit:

```powershell
git add frontend/src/features/promptLibrary/CompositionBoard.tsx frontend/src/features/promptLibrary/CombinationPicker.tsx frontend/src/features/promptLibrary/CombinationEditorModal.tsx frontend/src/features/promptLibrary/PromptWorkbench.test.tsx
git commit -m "feat: compose and save prompt combinations"
```

### Task 6: Descriptor-driven direct generation panel

**Files:**

- Create: `frontend/src/features/promptLibrary/GenerationPanel.tsx`
- Create: `frontend/src/features/promptLibrary/GenerationPanel.test.tsx`

- [ ] **Step 1: Write failing workflow filtering and payload tests**

```typescript
it("renders descriptor-supported fields and always renders seed mode", () => {
  render(<GenerationPanel forms={formsWithDefaultAndImageWorkflow} compose={composeResult} />);
  expect(screen.getByRole("option", { name: "default" })).toBeInTheDocument();
  expect(screen.queryByRole("option", { name: "pose" })).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Workflow"), { target: { value: "default" } });
  expect(screen.getByLabelText("Checkpoint")).toBeInTheDocument();
  expect(screen.getByLabelText("Steps")).toHaveAttribute("placeholder", "31");
  expect(screen.getByLabelText("Seed 模式")).toBeInTheDocument();
});

it("omits blank overrides and submits composed prompts with random seed", async () => {
  render(<GenerationPanel forms={forms} compose={composeResult} />);
  chooseWorkflow("default");
  chooseSeedMode("random");
  fireEvent.click(screen.getByRole("button", { name: "送出生圖" }));
  await waitFor(() => expect(promptLibraryApi.generate).toHaveBeenCalledWith({
    template: "default",
    prompt: composeResult.positive_prompt,
    negative_prompt: composeResult.negative_prompt,
    use_workflow_defaults: true,
    seed_mode: "random",
  }));
});

it("requires a number only for fixed seed", async () => {
  render(<GenerationPanel forms={forms} compose={composeResult} />);
  chooseWorkflow("default");
  chooseSeedMode("fixed");
  fireEvent.click(screen.getByRole("button", { name: "送出生圖" }));
  expect(await screen.findByText("固定 Seed 必填")).toBeInTheDocument();
  expect(promptLibraryApi.generate).not.toHaveBeenCalled();
});
```

Also test workflow-default seed, explicit steps/CFG/dimensions/batch/sampler/scheduler/model components/denoise, ordered multi-LoRA values and strengths, error display, job id, and 3-second queue polling cleanup.

- [ ] **Step 2: Run the panel test and confirm failure**

```powershell
npm test -- src/features/promptLibrary/GenerationPanel.test.tsx
```

Expected: collection fails because `GenerationPanel.tsx` is absent.

- [ ] **Step 3: Implement descriptor-controlled form state**

The panel is collapsible and disabled only when no workflow or positive prompt is available; the rest of the workbench remains usable. Default `use_workflow_defaults` to true and seed mode to random. Render a field only when its descriptor exists, except seed mode which is always rendered. Empty controls show workflow defaults as placeholders and are absent from the request. Render `loras` as `slot_count` ordered rows with installed-resource selects plus `strength_model` and optional `strength_clip`; omit empty rows.

Allow the user to turn workflow defaults off. In that mode, still send only entered overrides; backend legacy defaults supply steps/CFG, and seed mode remains random/fixed (hide or disable workflow-default seed). In workflow-default mode, offer all three seed modes.

- [ ] **Step 4: Implement submit, job result, and queue polling**

Submit exact server-composed positive and negative strings. Include `template`, `use_workflow_defaults`, and `seed_mode`; include fixed seed and non-empty descriptor-supported overrides only. Poll `/api/generate/queue` immediately and every 3000 ms, clear the interval on unmount, show running/pending counts, and display the returned job id. Normalize failures through `ApiError`.

- [ ] **Step 5: Run tests and commit**

```powershell
npm test -- src/features/promptLibrary/GenerationPanel.test.tsx
npm run typecheck
```

Expected: all panel tests and typecheck pass.

Commit:

```powershell
git add frontend/src/features/promptLibrary/GenerationPanel.tsx frontend/src/features/promptLibrary/GenerationPanel.test.tsx
git commit -m "feat: generate from prompt workbench"
```

### Task 7: Unified workbench layout and route integration

**Files:**

- Create: `frontend/src/features/promptLibrary/PromptWorkbench.tsx`
- Modify: `frontend/src/pages/Generate.tsx`
- Modify: `frontend/src/App.tsx:14-27`
- Modify: `frontend/src/pages/Dashboard.tsx`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/features/promptLibrary/PromptWorkbench.test.tsx`

- [ ] **Step 1: Add the end-to-end component test**

Mock feature API calls and exercise this exact browser-level flow:

```typescript
it("searches, composes, saves, copies, and queues a text-to-image job", async () => {
  render(<PromptWorkbench />);
  fireEvent.change(screen.getByRole("searchbox", { name: "模糊搜尋" }), { target: { value: "洋裝" } });
  await vi.advanceTimersByTimeAsync(250);
  fireEvent.click(await screen.findByRole("button", { name: "加入 連身裙" }));
  fireEvent.click(screen.getByRole("tab", { name: "Negative" }));
  fireEvent.click(screen.getByRole("button", { name: "加入 低品質" }));
  fireEvent.change(screen.getByLabelText("連身裙 權重"), { target: { value: "1.2" } });
  fireEvent.click(screen.getByRole("button", { name: "複製 Positive Prompt" }));
  fireEvent.click(screen.getByRole("button", { name: "儲存常用組合" }));
  fireEvent.change(screen.getByLabelText("Workflow"), { target: { value: "default" } });
  fireEvent.change(screen.getByLabelText("Seed 模式"), { target: { value: "random" } });
  fireEvent.click(screen.getByRole("button", { name: "送出生圖" }));
  expect(await screen.findByText(/已加入佇列/)).toBeInTheDocument();
  expect(navigator.clipboard.writeText).toHaveBeenCalledWith("(dress:1.2)");
});
```

Add a route smoke test that starts at `/generate` and finds `Prompt 工作台`.

- [ ] **Step 2: Run integration tests and confirm failure**

```powershell
npm test -- src/features/promptLibrary/PromptWorkbench.test.tsx src/App.test.tsx
```

Expected: tests fail because the workbench and route label are not integrated.

- [ ] **Step 3: Assemble the unified responsive page**

`PromptWorkbench` owns only composition coordination and active browser filters; generation state remains inside `GenerationPanel`. Use:

```tsx
<div className="grid gap-4 lg:grid-cols-[16rem_minmax(0,1fr)_22rem]">
  <LibrarySidebar />
  <main className="min-w-0 space-y-4">
    <EntryBrowser />
    <CompositionBoard />
  </main>
  <aside className="min-w-0 space-y-4">
    <CombinationPicker />
    <GenerationPanel />
  </aside>
</div>
```

On smaller screens the grid stacks. Keep both prompt lanes visible. Switching polarity changes browsing/add target but never hides or clears the other lane. Mount editors at page root so dialogs are not clipped.

- [ ] **Step 4: Replace the old page and update navigation copy**

Make `pages/Generate.tsx` return `<PromptWorkbench />`; do not retain its duplicate fetch/polling/form code. Keep route `/generate`, rename the nav link `Prompt 工作台`, and update the dashboard card to state that users can compose/copy prompts or send them through a text-to-image workflow.

- [ ] **Step 5: Run tests and commit**

```powershell
npm test -- src/features/promptLibrary/PromptWorkbench.test.tsx src/App.test.tsx
npm run typecheck
npm run build
```

Expected: tests, typecheck, and production build all exit 0.

Commit:

```powershell
git add frontend/src/features/promptLibrary/PromptWorkbench.tsx frontend/src/features/promptLibrary/PromptWorkbench.test.tsx frontend/src/pages/Generate.tsx frontend/src/App.tsx frontend/src/pages/Dashboard.tsx frontend/src/App.test.tsx
git commit -m "feat: ship unified prompt workbench"
```

### Task 8: Full human-facing verification and progress checkpoint

**Files:**

- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: Run focused backend generation coverage**

```powershell
python -m pytest backend/tests/test_workflow_generation_form.py backend/tests/test_generate_api.py backend/tests/test_queue.py backend/tests/test_workflow.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run all frontend checks**

```powershell
Set-Location frontend
npm run typecheck
npm test
npm run build
Set-Location ..
```

Expected: typecheck, all Vitest files, and the Vite production build exit 0.

- [ ] **Step 3: Run backend regression**

```powershell
python -m pytest backend/tests/ -x -q
```

Expected: backend suite exits 0 with no first failure.

- [ ] **Step 4: Perform a local UI smoke test**

Start backend and frontend using `docs/setup-guide.md`. In `/generate`, verify: category browse; Chinese/English fuzzy search; positive/negative multi-select; free text; inline entry creation; weight/order; two clipboard buttons; save/load combination; entry correction reflected after reload; eligible workflow filtering; workflow defaults; random seed; fixed seed; one queued job; and queue status. Use a mock/available ComfyUI instance appropriate to the local environment and record whether the submitted job reached recording/gallery.

- [ ] **Step 5: Document evidence and commit**

Add a dated `Prompt Workbench UI + workflow generation` entry to `docs/PROGRESS.md` with focused/full command results and smoke-test outcome. State that MCP agent parity remains the final plan-set stage.

```powershell
git add docs/PROGRESS.md
git commit -m "docs: record prompt workbench progress"
git status --short
```

Expected: the commit succeeds and the working tree is clean.
