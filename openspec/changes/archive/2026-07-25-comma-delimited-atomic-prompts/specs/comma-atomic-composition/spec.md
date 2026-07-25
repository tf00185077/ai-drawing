## ADDED Requirements

### Requirement: ASCII comma is the unconditional composition boundary
The Workbench SHALL treat every ASCII comma U+002C as a boundary between adjacent prompt segments. For every non-empty lane it SHALL derive segments with behavior equivalent to `raw.split(",")`, retain each exact segment string, and reconstruct the lane with behavior equivalent to `segments.join(",")`. It MUST NOT recognize parentheses, weights, quotes, backslashes, CSV quoting, or any escape syntax as exceptions. An entirely empty lane SHALL contain zero segments; all other input, including whitespace-only input, SHALL contain the exact split segments.

#### Scenario: Leading trailing and consecutive commas create empty slots
- **WHEN** the user enters `a,,b,` in a final prompt textarea
- **THEN** the Workbench displays four segments with exact values `a`, ``, `b`, and ``, in that order
- **AND** reconstructing those segments produces exactly `a,,b,`

#### Scenario: Commas inside quotes parentheses and weights still split
- **WHEN** the user enters `"a,b",(c,d:1.2)` in a final prompt textarea
- **THEN** the Workbench creates four segments at all three U+002C boundaries without interpreting quote or parenthesis syntax
- **AND** the visible textarea remains exactly `"a,b",(c,d:1.2)`

#### Scenario: Non-ASCII comma is ordinary text
- **WHEN** the user enters `a，b` using U+FF0C
- **THEN** the Workbench displays one segment containing exactly `a，b`

#### Scenario: Entirely empty lane has no segment
- **WHEN** a prompt lane's raw text is exactly the empty string
- **THEN** the lane contains zero segments and no blank-fragment error

#### Scenario: Free-text Add atomizes every comma
- **WHEN** the user adds free text `a,,b`
- **THEN** the lane receives exact atoms `a`, ``, and `b`
- **AND** Generate, Save, Update, or Save As preflight reports the new blank atom before any request

#### Scenario: Card content edit atomizes every comma
- **WHEN** the user changes one card content field to `a,,b`
- **THEN** that card becomes three literal cards containing `a`, ``, and `b`
- **AND** the lane reconstructs exactly `a,,b` without hiding a comma inside one fragment

### Requirement: Final textarea editing is lossless and caret-safe
The Positive and Negative final textareas SHALL always be directly editable after Backend readiness is true. Each structured segment SHALL contain exact unweighted `snapshotRaw` (the Backend `snapshot` field), numeric `weight`, and derived `renderedRaw=render(snapshotRaw, weight)`. Frontend SHALL canonicalize finite editable weights to Backend's at-most-three-decimal form before rendering, sending, or comparing. The final textarea SHALL equal `renderedAtoms.join(",")`. On each input event the Workbench SHALL first store the browser's exact value, split it into edited rendered atoms, derive cards without normalizing that value, and preserve the current selection and caret. Reconciliation MUST compare exact `renderedRaw`. Exact non-overlapping common-prefix and common-suffix matches MAY retain UI identity, `snapshotRaw`, weight, and genuine source metadata; every changed or ambiguous middle rendered atom MUST become a literal with `snapshotRaw` equal to the exact edited atom, weight 1, and no source ref. The Workbench MUST NOT parse apparent weight syntax from edited textarea text. A segment created by direct typing MUST remain literal even if its text matches a catalog prompt.

#### Scenario: Typing a comma immediately adds a card without moving caret
- **WHEN** the caret is in the middle of a final textarea and the user types one ASCII comma
- **THEN** the exact browser value remains visible
- **AND** one additional adjacent segment card appears immediately
- **AND** the caret remains at the browser-reported position after the inserted comma

#### Scenario: Editing a referenced segment removes provenance only from the changed region
- **WHEN** a lane contains referenced segments `a,b,c` and the user changes the middle text to produce `a,custom,c`
- **THEN** the first and last unchanged segments retain their original UI identities and source refs
- **AND** the middle segment becomes `kind=literal` with `snapshotRaw=custom`, weight 1, and no `ref` or `source_revision`

#### Scenario: Inserting a segment does not shift source identity
- **WHEN** a lane contains two referenced segments and the user inserts `new,` between them in the final textarea
- **THEN** the exact unchanged prefix and suffix refs remain attached to their original text
- **AND** the inserted segment is a literal
- **AND** no ref is assigned by array position

#### Scenario: Typed catalog-equivalent token does not fabricate a ref
- **WHEN** the user directly types a token whose normalized text exactly matches one Prompt Library entry
- **THEN** the card remains a literal without a source ref
- **AND** saving serializes it as a literal

#### Scenario: Unchanged weighted segment preserves structured identity
- **WHEN** a loaded referenced segment has `snapshotRaw=detail`, weight 1.2, and `renderedRaw=(detail:1.2)` and the user edits a different atom
- **THEN** exact reconciliation preserves that segment's `snapshotRaw`, weight, ref, source revision, and UI identity
- **AND** the final textarea still contains exactly `(detail:1.2)` for that atom

#### Scenario: Editing weighted rendered text demotes without parsing
- **WHEN** a loaded referenced atom displays `(detail:1.2)` and the user changes that exact textarea atom to `(detail:1.3)`
- **THEN** the segment becomes a literal with `snapshotRaw=(detail:1.3)` and weight 1
- **AND** its `renderedRaw` remains exactly `(detail:1.3)`
- **AND** no source ref or parsed weight 1.3 is retained

#### Scenario: Editable weight uses Backend canonical precision
- **WHEN** the user enters weight `1.2345`
- **THEN** the visible rendered atom and outgoing structured weight use canonical `1.234`
- **AND** save response comparison, retry, and reload do not produce a stale etag or canonical mismatch

### Requirement: Cards preserve empty slots and exact raw segment text
The card collection SHALL contain empty and whitespace-only transient rendered segments, count them in pagination, and expose content edit, weight, reorder, and delete operations without trimming or filtering. Empty cards SHALL display the fixed label `自訂文字`, SHALL show an invalid state, and SHALL keep their exact content. Reorder SHALL move the exact structured segment. Delete SHALL remove the selected segment and the single adjacent delimiter needed to join the remaining rendered atoms deterministically.

#### Scenario: Empty slots participate in pagination
- **WHEN** a lane contains more than one page of segments including empty segments
- **THEN** page counts and total card counts include the empty segments
- **AND** navigating pages exposes each empty card at its actual sequence position

#### Scenario: Reordering an empty segment preserves delimiter count
- **WHEN** the user reorders an empty segment among non-empty segments
- **THEN** the Workbench moves that exact empty string in the segment array
- **AND** reconstructs the final text with one comma between every adjacent array element

#### Scenario: Deleting a trailing empty segment removes the trailing comma
- **WHEN** the lane is `a,b,` and the user deletes the third empty card
- **THEN** the lane becomes exactly `a,b`
- **AND** neither non-empty segment is trimmed or rewritten

#### Scenario: Filling an empty card clears its invalid state
- **WHEN** the lane is `a,,b` and the user changes the second card content to ` middle `
- **THEN** the lane becomes exactly `a, middle ,b`
- **AND** the second card is no longer blank or whitespace-only

### Requirement: Display labels are deterministic and independent of provenance
The Workbench SHALL choose labels using exact deterministic resolution only. A valid source ref with a non-empty `name_zh` SHALL use trimmed `name_zh`; a valid source ref without Chinese SHALL use the trimmed English prompt. A literal with exactly one catalog-wide exact normalized prompt match MAY use the same display hierarchy without gaining a ref. Empty, unresolved, fuzzy-only, or ambiguous tokens SHALL display the fixed fallback `自訂文字`. Labels SHALL be presentation-only, non-editable, omitted from persistence, and recomputed on every load. Users SHALL edit the prompt content field rather than a custom label. Matching SHALL normalize with Unicode NFKC, trim, whitespace collapse, and Unicode case folding without modifying stored raw text.

#### Scenario: Referenced entry uses Chinese label
- **WHEN** a saved or newly selected source entry has `name_zh=傑作` and prompt `masterpiece`
- **THEN** its card label is `傑作`
- **AND** the card retains the genuine source ref

#### Scenario: Unique typed token uses display label but remains literal
- **WHEN** a directly typed token has exactly one normalized catalog match whose `name_zh` is `傑作`
- **THEN** the card may display `傑作`
- **AND** the card remains an unreferenced literal

#### Scenario: Duplicate English tokens fail safe
- **WHEN** the same normalized English token exists in more than one category or polarity
- **THEN** an unreferenced matching token displays the fixed label `自訂文字`
- **AND** the Workbench does not choose a candidate or create a ref

#### Scenario: English fallback does not rewrite content
- **WHEN** a uniquely resolved entry has no Chinese name and its prompt is `  best quality  `
- **THEN** the card label is `best quality`
- **AND** the stored raw segment remains exactly `  best quality  `

#### Scenario: Fallback label is recomputed and not persisted
- **WHEN** an unresolved literal card is saved and later loaded
- **THEN** no custom display-label field is present in the saved fragment
- **AND** the Workbench recomputes and displays `自訂文字`
- **AND** the user can edit only the prompt content

### Requirement: Blank-segment preflight blocks all mutating and generation actions
The Workbench SHALL run one shared client-side preflight before Save, Update, Save As, and Generate. If any present rendered segment satisfies `segment.renderedRaw.trim() === ""` or its structured `snapshotRaw` is blank/whitespace-only, the action MUST stop before any Prompt Library, compose, or generation request is made. The Workbench MUST NOT drop, trim, canonicalize, or send the invalid segments. The error SHALL list every affected polarity and 1-based segment position, explain that every ASCII comma creates a prompt, and instruct the user to fill or remove each empty segment.

#### Scenario: Save reports all Positive blank positions
- **WHEN** the Positive lane is `a,,b,` and the user invokes Save
- **THEN** no network request is made
- **AND** the error identifies Positive segments 2 and 4
- **AND** it states that every ASCII comma creates a prompt which must be filled or removed

#### Scenario: Update reports blanks in both polarities
- **WHEN** Positive segment 2 and Negative segments 1 and 3 are blank or whitespace-only and the user invokes Update
- **THEN** no network request is made
- **AND** the error lists `正向第 2 段` and `負向第 1、3 段`
- **AND** the first invalid card is focused and its page is opened

#### Scenario: Save As is blocked before compose
- **WHEN** a lane has a trailing comma and the user invokes Save As
- **THEN** neither `/api/prompt-library/compose` nor a combination write endpoint is called
- **AND** the dirty document and exact trailing comma remain unchanged

#### Scenario: Generate is blocked before generation request
- **WHEN** either lane contains a blank or whitespace-only segment and the user invokes Generate
- **THEN** `/api/generate/` is not called
- **AND** no live generation job is created

#### Scenario: Empty unused Negative lane does not trigger blank preflight
- **WHEN** the Negative lane is exactly `raw=""` with zero segments and all present Positive segments are nonblank
- **THEN** blank-segment preflight passes
- **AND** any other generation validations still apply independently

### Requirement: Document operations preserve atomic round trips and dirty state
Load, Save, Update, and Save As SHALL use ordered atomic fragments and SHALL preserve exact `snapshotRaw`, delimiter count, refs, weights, derived `renderedRaw`, and warnings. Load or new-document replacement SHALL remain protected by the dirty guard. A successful save SHALL install the Backend canonical response and clear dirty state only when recomputing and joining every returned rendered atom equals the visible raw text. Joining unweighted Backend snapshots is not a valid equality check. A failed or stale request MUST preserve the latest local document.

#### Scenario: Save load round trip preserves exact text
- **WHEN** a valid nonblank composition containing original segment whitespace is saved and loaded
- **THEN** each loaded card has the same `snapshotRaw`, order, weight, `renderedRaw`, and genuine ref as the saved canonical fragment
- **AND** joining loaded `renderedRaw` values with U+002C reproduces the exact saved final textarea

#### Scenario: Non-one weight survives browser load save and reload
- **WHEN** the browser loads a referenced fragment with Backend `snapshot=detail` and weight 1.2
- **THEN** it displays `(detail:1.2)` while retaining the unweighted snapshot and ref
- **AND** Save followed by reload returns `snapshot=detail`, weight 1.2, the same ref, and visible `(detail:1.2)`

#### Scenario: Update uses loaded concurrency tokens
- **WHEN** the user loads a combination and invokes Update after a valid edit
- **THEN** the request uses the repaired detail response's current revision and etag
- **AND** does not use stale catalog-summary tokens

#### Scenario: Save As creates a new document
- **WHEN** the user invokes Save As with valid segments and a new ID
- **THEN** the request uses expected revision zero and no existing etag
- **AND** the original loaded combination remains unchanged

#### Scenario: Update and Save As preserve document metadata
- **WHEN** a loaded combination has non-default name, description, aliases, keywords, order, and `legacy_template`
- **THEN** Update submits those loaded values unchanged
- **AND** Save As intentionally copies those values to the new document rather than replacing them with Workbench defaults

#### Scenario: Dirty guard protects temporary empty slots
- **WHEN** the document is dirty and contains a temporary trailing empty segment
- **THEN** loading another combination or creating a blank document requires explicit discard confirmation
- **AND** declining confirmation keeps the exact text and cards

#### Scenario: Stale response cannot overwrite a later edit
- **WHEN** a load or save response resolves after the user has made a newer local edit
- **THEN** the response does not replace the newer raw text, cards, dirty state, success state, or errors

### Requirement: Workbench waits for finalized Backend readiness
The frontend SHALL query only the catalog-independent migration status before initializing Prompt Library UI. It MUST NOT request catalog/list/search/category/entry/combination/compose data or enable the Workbench unless readiness is true, atomic Backend enforcement is active, and no migration marker or blocking migration diagnostic exists.

#### Scenario: Migration-required state does not read the catalog
- **WHEN** Backend reports readiness false or a migration marker
- **THEN** the frontend displays a non-editing migration-required state
- **AND** makes no ordinary Prompt Library catalog-dependent request

#### Scenario: Finalized state enables the editor
- **WHEN** Backend reports readiness true, atomic enforcement active, and no marker
- **THEN** the frontend may load the catalog and enable comma-atomic editing

### Requirement: Generation uses the exact validated visible composition
After blank preflight and existing generation validations pass, the Workbench SHALL construct the generation request from the exact visible Positive and Negative raw text. It SHALL NOT recompose from labels, trim segment whitespace, or infer refs. Real-browser acceptance for this capability SHALL inspect request construction without submitting live image generation.

#### Scenario: Valid generation request preserves raw text
- **WHEN** valid Positive text is `a, b` and valid Negative text is `bad anatomy, blurry`
- **THEN** the generation request contains those exact strings as `prompt` and `negative_prompt`
- **AND** the Workbench does not normalize either to a different separator style

#### Scenario: Browser acceptance stops before live generation
- **WHEN** real-browser acceptance reaches the Generate action
- **THEN** it verifies the preflight and constructed request payload using interception or a non-live boundary
- **AND** it does not require a service restart, ComfyUI execution, or live image output
