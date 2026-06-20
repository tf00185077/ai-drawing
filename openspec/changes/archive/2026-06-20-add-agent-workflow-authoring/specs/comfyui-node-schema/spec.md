## ADDED Requirements

### Requirement: Node search returns matching node types by name and category

The system SHALL expose a `search_nodes` operation that queries the live ComfyUI node catalog (`/object_info`) and returns matching node types as lightweight `{name, category}` entries, without the full schema of any node. The operation SHALL support a `query` filter (node name substring) and a `category` filter (node category substring), both case-insensitive and combined with AND.

#### Scenario: Search by keyword returns matching node names

- **WHEN** an agent calls `search_nodes` with query `"KSampler"`
- **THEN** the response lists node types whose name contains `KSampler` (e.g. `KSampler`, `KSamplerAdvanced`) with each entry's `category`
- **AND** the response does NOT include the full input/output schema of any node

#### Scenario: Search by category filters by function

- **WHEN** an agent calls `search_nodes` with `category="loaders"`
- **THEN** the response lists only node types whose category contains `loaders`
- **AND** a `query` and `category` given together match only nodes satisfying both

#### Scenario: Search reflects the live instance

- **WHEN** a custom node is installed on the ComfyUI instance and matches the query
- **THEN** that custom node type appears in the `search_nodes` result
- **AND** a node type absent from the instance does not appear

#### Scenario: No match returns an empty result, not an error

- **WHEN** `search_nodes` is called with filters that match no node type
- **THEN** the system returns an empty list as data rather than a tool failure

### Requirement: Node search is bounded to protect agent context

The system SHALL require at least one of `query` or `category` for `search_nodes` and SHALL reject a call with neither, so the whole catalog can never be dumped in one search. The system SHALL additionally cap the number of node entries returned per call to a default limit so a broad-but-present filter cannot flood the agent's context. The matches SHALL be deterministically ordered and the system SHALL support an `offset` so that every matching node remains reachable by paging, while each page stays bounded. The response SHALL report the true total match count, whether more results remain, and the next page offset.

#### Scenario: Search with no filter is rejected

- **WHEN** `search_nodes` is called with neither `query` nor `category`
- **THEN** the system returns an error directing the agent to supply a filter or browse categories first
- **AND** does not return any node entries

#### Scenario: Broad search is capped and flagged as truncated

- **WHEN** a search matches more node types than the result limit
- **THEN** the response returns at most the limit number of entries
- **AND** reports the full match `total`, a `truncated` indicator, and a `next_offset` to continue

#### Scenario: Remaining matches are reachable by paging

- **WHEN** a search is truncated and the agent calls again with `offset` set to the reported `next_offset`
- **THEN** the response returns the next bounded page of matches in deterministic order
- **AND** the final page reports `truncated` false so every matching node is reachable without ever returning the whole catalog at once

#### Scenario: Category listing lets the agent browse before searching

- **WHEN** an agent lists node categories
- **THEN** the response returns each category with its node count
- **AND** the agent can then call `search_nodes` with a `category` to narrow results without dumping the whole catalog

### Requirement: Node schema query returns a single node's input/output spec

The system SHALL expose a `get_node_schema` operation that returns the input names, input types, and output types for one named node type, so the agent can construct valid connections without dumping the entire catalog.

#### Scenario: Schema returned for a known node

- **WHEN** an agent calls `get_node_schema` with `node_type="KSampler"`
- **THEN** the response includes the node's required and optional input names with their types
- **AND** the response includes the node's output types

#### Scenario: Unknown node type returns structured not found

- **WHEN** `get_node_schema` is called with a node type absent from the live instance
- **THEN** the system returns a structured not-found result naming the requested node type

### Requirement: Node schema source is the live ComfyUI instance with cache invalidation

The system SHALL source node schema from the live ComfyUI `/object_info` and MAY cache it, but the cache SHALL be invalidated when the ComfyUI instance changes (restart or custom-node change) so stale node types are not reported as available.

#### Scenario: Cache refreshed after instance change

- **WHEN** node schema has been cached and the ComfyUI instance is restarted with a different node set
- **THEN** a subsequent `search_nodes` / `get_node_schema` call reflects the new node set rather than the stale cached set
