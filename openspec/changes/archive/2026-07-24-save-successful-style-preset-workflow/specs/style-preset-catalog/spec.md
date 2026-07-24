## ADDED Requirements

### Requirement: Explicit save promotes a successful generated graph into a style preset

The system SHALL save a style-preset workflow only when an agent explicitly invokes the save operation with a source that resolves to a successfully generated image-compatible Gallery record containing the actual submitted `workflow_json`. The save path SHALL NOT run automatically after generation and SHALL NOT rebuild a graph from the preset recipe.

#### Scenario: Successful Gallery image is accepted

- **GIVEN** a Gallery image belongs to a completed generation and stores a JSON-object `workflow_json`
- **WHEN** the explicit save operation names that image and a known preset/profile
- **THEN** the backend copies that recorded graph as the source for the saved preset workflow
- **AND** the original Gallery record remains unchanged

#### Scenario: Completed job locator resolves its recorded graph

- **GIVEN** a completed image-generation job has one or more recorded image outputs sharing its submitted graph
- **WHEN** the save operation supplies that job locator
- **THEN** the backend resolves the recorded graph without requiring the caller to transfer workflow JSON

#### Scenario: Missing or unsuccessful source does not write

- **WHEN** the source is missing, incomplete, failed, video-only, lacks workflow JSON, or its workflow is not a JSON object
- **THEN** the backend returns a structured repairable error
- **AND** no style-preset workflow file is created or replaced

### Requirement: Saved prompt text contains only caller-supplied keywords

The save operation SHALL accept positive and negative keywords as a string or string list. It SHALL normalize syntax without semantic inference and SHALL replace only positive/negative conditioning text reachable from sampler inputs. Direct text strings SHALL be changed in place. A link-valued text input MAY preserve its link and change an upstream Primitive/String carrier only when the carrier exclusively supplies targeted conditioning text of one polarity. It SHALL use the source record's exact nonempty prompt fields as fail-closed evidence and SHALL NOT persist either exact full prompt anywhere in the complete graph.

#### Scenario: String and list keywords normalize deterministically

- **WHEN** keywords contain comma/newline separators, surrounding whitespace, empty entries, or exact duplicates
- **THEN** the backend trims entries, removes empties and exact duplicates in first-seen order, and joins them with `, `
- **AND** it does not add, translate, rank, or reorder semantic content

#### Scenario: Both polarities are replaced by graph reachability

- **GIVEN** sampler positive and negative links reach distinct `CLIPTextEncode` nodes
- **WHEN** the graph is saved
- **THEN** positive-reachable text nodes contain only normalized positive keywords
- **AND** negative-reachable text nodes contain only normalized negative keywords
- **AND** every non-text graph value and link remains equal to the successful source graph

#### Scenario: Shared polarity node is rejected

- **GIVEN** the same text-encoding node is reachable from both positive and negative sampler inputs
- **WHEN** different positive and negative keywords are supplied
- **THEN** the backend returns `ambiguous_conditioning`
- **AND** does not restructure or save the graph

#### Scenario: No positive conditioning is rejected

- **WHEN** no positive-reachable text encoder can be resolved
- **THEN** the backend returns `conditioning_not_found`
- **AND** does not guess based on node titles

#### Scenario: Exclusive linked text carrier preserves graph semantics

- **GIVEN** a sampler-reachable `CLIPTextEncode.inputs.text` links to a Primitive/String carrier
- **AND** every consumer of that carrier is targeted conditioning text of one polarity
- **WHEN** the graph is saved
- **THEN** the link remains unchanged
- **AND** the carrier's unambiguous string value contains the normalized keywords
- **AND** no unrelated graph value changes

#### Scenario: Unsafe linked text carrier is rejected

- **GIVEN** a linked text carrier is unsupported, ambiguous, shared across polarities, or has a non-conditioning consumer
- **WHEN** the graph is saved
- **THEN** the backend returns a structured repairable error
- **AND** does not replace the link or guess which carrier field is prompt text
- **AND** creates or replaces no output file

#### Scenario: Exact source prompt elsewhere is rejected

- **GIVEN** targeted conditioning text has been replaced
- **AND** an orphan encoder, metadata field, mapping key, nested value, or other graph location still contains a nonempty exact source `prompt` or `negative_prompt`
- **WHEN** the sanitizer inspects the complete graph
- **THEN** the backend returns `prompt_confidentiality_unproven`
- **AND** does not delete or mutate the unrelated location
- **AND** creates or replaces no output file

### Requirement: Saved workflow is a strict raw ComfyUI API graph

The backend SHALL atomically save the sanitized graph at `style_presets/agent/workflows/<preset-id>/<profile-or-__base__>.api.json`. The file SHALL contain only the ComfyUI API node object and SHALL NOT contain a manifest, source metadata, hash, snapshot id, response envelope, or full round prompt.

The capability SHALL apply uniformly to every known style preset and SHALL NOT depend on Niji, Anima, a checkpoint family, a template name, fixed node ids, or a fixed number of LoRA/model loader nodes.

#### Scenario: Structurally different preset graphs use the same save path

- **GIVEN** two successful style-preset generations use different model families, node ids/order, and loader counts
- **WHEN** each is explicitly saved
- **THEN** both are sanitized by conditioning-link reachability and written through the same generic backend operation
- **AND** neither requires a preset-specific branch or hard-coded template knowledge

#### Scenario: Known profile is saved at its conventional path

- **WHEN** a known preset and profile are saved successfully
- **THEN** the target path is derived by the backend from the canonical preset/profile
- **AND** the file parses as a JSON object whose nodes contain string `class_type` and object `inputs`

#### Scenario: Base preset uses the base filename

- **WHEN** no profile is supplied
- **THEN** the graph is saved as `<preset-id>/__base__.api.json`

#### Scenario: Existing graph is atomically replaced

- **GIVEN** a saved graph already exists for the preset/profile
- **WHEN** the user explicitly saves a later successful graph
- **THEN** the backend atomically replaces the target file
- **AND** readers never observe a partially written JSON file

#### Scenario: Raw graph can be retrieved directly

- **WHEN** a client requests the saved workflow for a known preset/profile
- **THEN** the backend returns the raw ComfyUI API graph as the JSON response body
- **AND** no LLM or generation-payload composition is involved

### Requirement: Saved style preset workflow can be retested verbatim

The system SHALL provide a server-owned retest operation that reads the saved graph and submits it without applying runtime overrides or custom-workflow default prompts.

#### Scenario: Retest preserves saved graph values

- **GIVEN** a saved workflow contains keyword text and fixed sampler/model values
- **WHEN** the retest operation queues it
- **THEN** the submitted ComfyUI graph preserves those exact values
- **AND** the queue does not call `apply_params` or inject `1girl, solo`, seed, steps, cfg, dimensions, or model components

#### Scenario: Missing saved workflow is repairable

- **WHEN** a client requests retest for a preset/profile without a saved graph
- **THEN** the backend returns `saved_workflow_not_found`
- **AND** no generation job is queued

#### Scenario: ComfyUI rejection remains observable

- **WHEN** ComfyUI rejects the saved graph
- **THEN** the queued job becomes terminal `failed`
- **AND** existing generation status exposes structured node errors
