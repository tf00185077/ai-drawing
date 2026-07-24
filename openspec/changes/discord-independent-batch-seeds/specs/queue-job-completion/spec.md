## ADDED Requirements

### Requirement: Independent parent lifecycle is aggregate and monotonic

The queue SHALL expose each independent batch once under its public parent ID.
The parent SHALL be `queued` before its first child starts, SHALL become
`running` when the first child starts, and SHALL remain `running` until every
member reaches a terminal outcome. Status SHALL expose additive total,
successful, failed, current-member, and sanitized failed-member fields.

#### Scenario: Parent status never regresses between children

- **WHEN** one child finishes and a later sibling is still queued
- **THEN** the public parent remains `running`
- **AND** never returns to `queued`

#### Scenario: Queue status lists a parent once

- **WHEN** an independent parent has multiple queued or running children
- **THEN** aggregate queue status contains one public entry for that parent
- **AND** no child execution ID appears

### Requirement: Parent completion derives from every member outcome

The queue SHALL make a parent terminal only after every requested member is
terminal. It SHALL mark the parent `completed` when at least one member
succeeded, including mixed outcomes, and SHALL mark it `failed` only when no
member produced a successful image.

#### Scenario: Mixed outcomes complete the parent

- **WHEN** three members succeed and one member fails
- **THEN** the parent becomes `completed` after the fourth member terminates
- **AND** reports `batch_completed=3` and `batch_failed=1`
- **AND** returns the three successful artifacts and one sanitized failed-member
  summary

#### Scenario: Zero successful members fail the parent

- **WHEN** every requested member reaches a failed terminal state
- **THEN** the parent becomes `failed`
- **AND** returns no successful image artifacts
- **AND** reports total, completed, and failed counts from the durable aggregate
- **AND** reports bounded per-member reasons without replacing them with the
  final child's raw `node_errors`

### Requirement: Member failures do not cancel siblings

A failed independent member SHALL be accounted terminally without removing or
cancelling later siblings. Queue running capacity SHALL be released for every
member outcome, including malformed ComfyUI submission responses and recording
errors.

#### Scenario: Later siblings continue after child two fails

- **WHEN** child two of four fails
- **THEN** children three and four remain queued and execute normally

#### Scenario: Malformed submission releases the running slot

- **WHEN** a child receives a malformed ComfyUI submit response
- **THEN** that child is recorded failed
- **AND** the running slot is released
- **AND** the next queued sibling can start

#### Scenario: Recording error releases the running slot

- **WHEN** saving or recording a successful child raises an error
- **THEN** that child is recorded failed with a sanitized reason
- **AND** the running slot is released
- **AND** later siblings continue

#### Scenario: Transient malformed queue response preserves the running child

- **WHEN** ComfyUI returns one malformed `/queue` payload for a known prompt ID
- **AND** history does not yet contain a terminal response
- **THEN** the Backend retains the running slot
- **AND** does not start the next sibling early

#### Scenario: Terminal history resolves malformed queue state

- **WHEN** `/queue` is malformed but history for the known prompt ID is terminal
- **THEN** the Backend processes that terminal history normally
- **AND** completes or fails the current child from the terminal result

#### Scenario: Persistent queue and history uncertainty is bounded

- **WHEN** queue and history polling persistently cannot determine terminal
  status through the bounded retry budget
- **THEN** the Backend records the current child failed
- **AND** releases the running slot
- **AND** later siblings continue

### Requirement: Independent terminal outcomes are durable across restart

The Backend SHALL persist one parent row and one member row per requested image,
including member ordinal, seed, terminal status, and sanitized structured
failure. A fresh process/session SHALL derive aggregate status from persisted
member state. On startup, unfinished members whose in-memory executions were
lost SHALL become failed with stable `backend_restarted` reason while completed
members remain unchanged.

#### Scenario: Persisted mixed counts survive restart

- **WHEN** a terminal parent has three successful members and one failed member
  and the Backend status facade is recreated with a fresh database session
- **THEN** the parent remains `completed`
- **AND** still reports three successes, one failure, and the failed-member
  record

#### Scenario: Restart reconciles unfinished members

- **WHEN** startup finds a persisted independent parent with completed members
  and non-terminal members but no in-memory executions
- **THEN** completed members remain completed
- **AND** unfinished members become failed with code `backend_restarted`
- **AND** the parent is `completed` if any member succeeded, otherwise `failed`

#### Scenario: Persisted failure excludes raw collaborator payloads

- **WHEN** a ComfyUI or recording failure contains raw or secret-bearing data
- **THEN** durable member state contains only a stable failure code and bounded
  sanitized message

### Requirement: Independent queue admission is atomic

Capacity checking, seed allocation, durable batch creation, and child enqueue SHALL
occur as one atomic admission operation. Independent mode consumes one
queue slot per child, and insufficient capacity SHALL leave no visible parent
or child work.

#### Scenario: Capacity reserves every child together

- **WHEN** capacity can accept all children in an independent batch
- **THEN** all children become queued under one parent atomically

#### Scenario: Insufficient capacity enqueues nothing

- **WHEN** remaining capacity is smaller than the requested independent child
  count
- **THEN** admission fails
- **AND** zero children and no partial parent become queued

### Requirement: Queued parent cancellation is atomic

Cancelling a parent whose children are all queued SHALL remove every child as
one locked operation and leave no orphan sibling. Once any child is running,
parent cancellation SHALL retain the existing conflict response.

#### Scenario: Queued parent cancellation removes all children

- **WHEN** a caller cancels a fully queued independent parent
- **THEN** every queued child is removed atomically
- **AND** no child later starts

#### Scenario: Running parent cancellation conflicts

- **WHEN** a caller attempts to cancel an independent parent after a child has
  started
- **THEN** the Backend returns the existing HTTP 409 running-job behavior
