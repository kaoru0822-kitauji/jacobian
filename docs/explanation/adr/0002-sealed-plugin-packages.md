# ADR 0002: Seal plugin packages and registry snapshots

[Documentation home](../../index.md) · [Decision log](index.md)

- Status: Accepted for the provisional M3 implementation
- Date: 2026-07-24

## Decision

Treat an operator-installed Python source package as one sealed implementation
unit. Installation creates an immutable registry snapshot binding:

- plugin manifest and capability contracts;
- each declared entrypoint and implementation descriptor;
- the whole-package source digest for each implementation package;
- Python runtime, build identity, platform, system, and machine.

Discovery measures package files without importing package code. Capability
resolution remeasures the source and rejects changed bytes or an incompatible
runtime before worker execution.

The initial format hashes every regular package file. Declared and imported
package modules must be Python source; path escape, symlinks, bytecode-only
module execution, and native extension-module execution are rejected.

## Rationale

An entrypoint string and a digest of one file are not enough to reconstruct
what Python will import. Sibling modules and package initializers can affect
behavior. Measuring the package as a unit gives every capability one explicit,
replayable implementation identity.

Importing a package during discovery would execute operator-installed code
before validation and make enumeration stateful. Source inspection keeps
discovery deterministic and side-effect free.

Runtime and platform bindings are included because identical source bytes may
behave differently under another interpreter or binary dependency environment.
These bindings are compatibility evidence, not a claim of bit-for-bit
reproducibility.

## Conformance decision

The generic fault matrix runs against a disposable synthetic package in
isolated state. Production plugins do not expose inputs that deliberately hang,
crash, or emit malformed responses. Each suite run uses fresh invocation
identities and drives the real registry, search, worker, and conjecture
boundaries.

## Alternatives considered

### Import entrypoints and inspect callables

Rejected because discovery would execute package code and could observe a
different environment from the worker.

### Hash only the entrypoint file

Rejected because imported sibling modules could change without changing the
registered digest.

### Build a package manager or container-image pipeline

Deferred. Jacobian needs immutable local identity before it needs remote
distribution. A container can strengthen host isolation later without changing
the artifact and capability contract.

### Accept wheels, bytecode, and native modules immediately

Deferred until their complete executable closure can be measured and tested
across supported platforms.

## Consequences

- Any measured package-file change invalidates capabilities from that package.
- Dynamically generated or editable package behavior is unsuitable for a
  replayable installed plugin.
- Runtime compatibility failures occur before execution.
- Operators still decide whether code is safe for the host; sealing is not
  sandboxing.
- New package formats need their own measurement rules and conformance cases.
