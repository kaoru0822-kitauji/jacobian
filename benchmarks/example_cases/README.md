# Capability example pilot

`pilot.json` is the review ledger for the initial evidence-backed example
pilot. It is deliberately not a second public example API.

Schema-valid, directly invocable examples remain on
`CapabilityDescriptor.invocation_examples`, where capability registration
validates them against the installed descriptor schema and
`capability.describe` exposes them to clients.

The pilot ledger covers cases that cannot be represented by that valid-only
field:

- invalid and boundary outcomes;
- artifact-dependent producer-to-verifier workflows;
- repository source locations;
- required validation layers; and
- the human-review gate.

Existing integration tests at each `source` location execute the corresponding
public capability path and assert stable semantics. A case is not approved for
broader documentation merely because its test passes.
