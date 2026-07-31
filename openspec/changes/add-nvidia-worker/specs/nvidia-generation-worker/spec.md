# NVIDIA generation worker

## ADDED Requirements

### Requirement: Generation target is explicit

The system SHALL accept `local` or `worker` as a generation execution target,
default to `local`, and SHALL NOT silently retry a failed Worker job locally.

#### Scenario: Selected Worker is unavailable

- **WHEN** a request explicitly selects `worker`
- **AND** the paired Worker cannot be reached or authenticated
- **THEN** the job terminates with a structured failure
- **AND** no prompt is submitted to the local ComfyUI instance

### Requirement: Worker resource transfer is content verified

The coordinator SHALL transfer only workflow-referenced resources absent from
the Worker cache. The Worker SHALL verify declared size and SHA-256 before an
atomic promotion and SHALL NOT expose partial files to ComfyUI.

#### Scenario: Interrupted model upload

- **WHEN** a resource upload stops before the declared byte count
- **THEN** the partial content remains outside the ComfyUI model directory
- **AND** a later upload can resume from the accepted byte offset

### Requirement: ComfyUI remains private to the Worker host

The Windows installation SHALL bind ComfyUI to loopback and expose only an
authenticated Worker API to the Private Windows network profile.

#### Scenario: Windows network is Public

- **WHEN** setup detects that the active network profile is Public
- **THEN** setup stops before creating an inbound firewall rule
- **AND** explains that the operator must change the profile to Private

### Requirement: Runtime versions are pinned and upgradeable

The Worker distribution SHALL carry a version manifest for Worker protocol,
Python, PyTorch CUDA source, ComfyUI, and custom nodes. An upgrade SHALL validate
a staged runtime before replacing the active runtime.

#### Scenario: Existing unrelated ComfyUI is present

- **WHEN** setup detects an older or unrelated ComfyUI installation
- **THEN** it installs the Worker into its owned root without modifying it
- **AND** reports the old path for a separately confirmed cleanup
