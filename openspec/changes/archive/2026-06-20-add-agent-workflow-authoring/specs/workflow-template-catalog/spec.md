## ADDED Requirements

### Requirement: Templates carry a machine-readable capability manifest

Each workflow template SHALL have an associated manifest containing a controlled-vocabulary set of capability tags. The manifest SHALL define both `modality` (single-valued enum: `txt2img` | `img2img` | `inpaint`) and `model_family` (single-valued, e.g. `sdxl`, `sd15`, `anima`) as required fields — neither may be omitted or null, so matching never falls into an "unknown family" gray zone. The manifest MAY additionally define `conditioning` (set, e.g. `controlnet_pose`) and `io` (set, e.g. `text`, `image_ref`, `mask`). A human-readable `description` MAY be present but SHALL NOT participate in matching decisions.

#### Scenario: Manifest exposes capability tags

- **WHEN** a client reads the manifest for the `inpaint` template
- **THEN** the manifest reports `modality=inpaint`, a non-null `model_family`, and `io` including `mask`
- **AND** any `description` text is returned as metadata only

#### Scenario: Tags are drawn from a controlled vocabulary

- **WHEN** a manifest is created or backfilled with a capability tag not in the controlled vocabulary
- **THEN** the system rejects or flags the manifest as invalid rather than silently accepting a free-form tag

#### Scenario: Missing required field is rejected

- **WHEN** a manifest omits `modality` or `model_family`
- **THEN** the system flags the manifest as invalid identifying the missing required field
- **AND** does not treat the absent field as a wildcard

### Requirement: Lightweight capability index avoids reading full workflow JSON

The system SHALL expose a lightweight index of templates and their capability manifests so an agent can judge template suitability without retrieving the full workflow JSON of each template.

#### Scenario: Index lists capabilities without full graphs

- **WHEN** an agent lists the template capability index
- **THEN** each entry includes the template id, its capability tags, and `description`
- **AND** the entry does NOT include the full ComfyUI workflow JSON

### Requirement: Reuse match is a deterministic binary superset test

The system SHALL determine whether an existing template can satisfy a need by the set test *template capability tags ⊇ required capability tags*. The match SHALL be deterministic and binary, with no fuzzy or partial scoring.

#### Scenario: Template that covers the requirement matches

- **WHEN** the required capabilities are `{modality: img2img, io: image_ref}` and a template's tags are `{modality: img2img, io: [image_ref, text]}`
- **THEN** the template is reported as a match
- **AND** the agent applies it through the existing template-name generation path

#### Scenario: Template missing a required capability does not match

- **WHEN** the required capabilities include `conditioning: controlnet_pose` and no template's tags include that conditioning
- **THEN** no template is reported as a match
- **AND** the agent is directed to self-author a workflow instead

#### Scenario: Strict matching prefers a miss over a wrong match

- **WHEN** the required `modality` differs from every template's `modality`
- **THEN** the result is a miss even if other tags overlap, because `modality` is a required member of the superset test

### Requirement: Backfill is gated on verified generation success

The system SHALL write a self-authored workflow back into the template catalog only after ComfyUI has produced an image and the generation has been recorded successfully. A submitted-but-unverified workflow SHALL NOT be promoted to a template.

#### Scenario: Promotion occurs only after a recorded image

- **WHEN** a self-authored custom workflow completes and its output image is recorded
- **THEN** the workflow shape is eligible for backfill into the catalog

#### Scenario: Failed or unrecorded generation is not promoted

- **WHEN** a self-authored custom workflow fails in ComfyUI or produces no recorded image
- **THEN** the workflow is NOT written into the catalog

### Requirement: Backfill dedupes on the capability key and files by family

The system SHALL use the capability tag-set as the dedup key when backfilling. When a template with the same capability key already exists, the system SHALL NOT add a duplicate entry. When no existing template has that key, the system SHALL add a new entry tagged with its capabilities and filed under its `modality` family.

#### Scenario: New capability key creates a new family-filed entry

- **WHEN** a verified workflow has a capability key not present in the catalog
- **THEN** a new template entry is created with that capability tag-set
- **AND** it is filed under its `modality` family

#### Scenario: Existing capability key is not duplicated

- **WHEN** a verified workflow's capability key already exists in the catalog
- **THEN** no duplicate entry is created

### Requirement: Templates are versioned, never mutated in place

The system SHALL NOT modify an existing shared template's graph in place during backfill. When an existing template's capability key must be re-populated (e.g. the prior template was broken), the system SHALL create a new version and mark the prior entry deprecated. The system SHALL NOT auto-merge two workflow graphs into one.

#### Scenario: Broken template superseded by a new version

- **WHEN** a verified workflow shares a capability key with an existing template that was broken
- **THEN** a new version entry is created and the prior entry is marked deprecated
- **AND** the prior entry's graph is left unmodified

#### Scenario: Similar template is only a build-time scaffold

- **WHEN** an agent self-authors using an existing similar template as a starting scaffold
- **THEN** the resulting verified workflow is saved as its own catalog entry
- **AND** the scaffold template is not mutated by the backfill

### Requirement: Backfilled templates store a reusable shape, not one-off content

When backfilling, the system SHALL store the parameterizable workflow shape and SHALL NOT bake in single-use values such as the specific content prompt or a fixed seed, so the template stays reusable through the existing parameter-injection path.

#### Scenario: Content prompt and seed are not frozen into the template

- **WHEN** a verified workflow whose prompt was `"a girl in a red raincoat"` with seed `12345` is backfilled
- **THEN** the stored template does not hardcode that content prompt or that seed
- **AND** the template remains parameterizable by `prompt` and `seed` at generation time
