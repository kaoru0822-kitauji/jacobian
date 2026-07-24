# Find and verify a counterexample

[Documentation home](../index.md)

This tutorial runs one bounded graph experiment from artifact creation through
independent witness verification. It demonstrates Jacobian's central trust
boundary: an evaluator may report a mathematical conclusion, but that
conclusion remains unverified until an authorized checker accepts the exact
evidence and bindings.

## Prerequisites

Use Python 3.12 and install the locked development environment from the
repository root:

```sh
uv sync --dev
```

## Create the experiment

Save the following as `first_verified_result.py`:

```python
from pathlib import Path

from jacobian.kernel import JacobianKernel


state_dir = Path(".jacobian-tutorial")
kernel = JacobianKernel(state_dir, install_references=True)
reference = kernel.references["graph_paths"]

claim = kernel.artifacts.put(
    schema_uri=reference.claim_schema_uri,
    semantics_uri=reference.semantics_uri,
    payload={
        "claim_schema_version": "1",
        "domain_id": "jacobian.graph-paths",
        "domain_version": "1",
        "semantics_uri": reference.semantics_uri,
        "quantifiers": [],
        "predicate": {
            "name": "intended_paths_complete",
            "parameters": {"simple": True},
        },
        "bounds": {},
        "required_capabilities": ["Evaluator", "WitnessOracle"],
        "correspondence_status": "HUMAN_REVIEWED",
    },
)

candidate = kernel.artifacts.put(
    schema_uri=reference.candidate_schema_uri,
    semantics_uri=reference.semantics_uri,
    payload={
        "vertices": ["s", "a", "b", "x", "t1", "t2"],
        "arcs": [
            ["s", "a"],
            ["a", "x"],
            ["s", "b"],
            ["b", "x"],
            ["x", "t1"],
            ["x", "t2"],
        ],
        "source": "s",
        "terminals": ["t1", "t2"],
        "intended_paths": [
            ["s", "a", "x", "t1"],
            ["s", "b", "x", "t2"],
        ],
    },
)

evaluation = kernel.evaluation.evaluate_batch(
    claim_uri=claim.artifact_uri,
    candidate_uris=(candidate.artifact_uri,),
    plugin_id=reference.plugin_id,
    profile="EXACT_CANDIDATE",
    seed=0,
    wall_seconds=30,
)
evaluated = evaluation.items[0].result
print("evaluation:", evaluated.conclusion.value, evaluated.assurance.verification.value)

found = kernel.witnesses.find(
    claim_uri=claim.artifact_uri,
    candidate_uri=candidate.artifact_uri,
    plugin_id=reference.plugin_id,
    witness_role="DEFEATS_CANDIDATE",
    wall_seconds=30,
)
assert found.witness_uri is not None

verified = kernel.verification.verify_witness(
    claim_uri=claim.artifact_uri,
    candidate_uri=candidate.artifact_uri,
    witness_uri=found.witness_uri,
    checker_id=reference.witness_checker_ids["graph.omitted_path"],
)
print("verification:", verified.conclusion.value, verified.assurance.verification.value)
print("witness:", found.witness_uri)
```

Run it:

```sh
uv run python first_verified_result.py
```

The important part of the output is:

```text
evaluation: FALSE UNVERIFIED
verification: FALSE VERIFIED
```

The evaluator found that the proposed path list is incomplete, but its result
did not cross the evidence boundary. The witness checker independently
validated an omitted path and produced a verified result bound to the claim,
candidate, witness, semantics, and checker identity.

## Inspect the durable state

The artifacts and verification record remain under `.jacobian-tutorial/`.
Running the script again reuses content-addressed artifacts rather than
changing their identity.

Continue with the [architecture explanation](../explanation/architecture.md)
to understand the trust zones, or consult the
[tool reference](../reference/tools.md) for the complete public surface.
