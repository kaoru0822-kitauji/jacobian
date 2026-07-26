# Capability development handoffs

The discovery, implementation, checker, and evaluation skills use the same
compact handoff shape. A handoff is a structured report in an issue, PR,
artifact, or transcript; it is not a new runtime API or a requirement to add a
durable file for every experiment.

## Common envelope

Use these fields whenever work moves between stages:

```yaml
stage: discovery
status: accepted
subject:
  candidate_id: ...
  capability_ids: [...]
evidence_refs:
  - ref: source locator, artifact URI, or report
    digest: optional content digest
contract_ref: ...
runtime_snapshot: ...
assurance: ...
open_obligations: [...]
missing_evidence: [...]
decision: ...
next_action: ...
```

`evidence_refs` must identify the exact source, case, artifact, or report being
relied on. Include content digests when a later stage must reproduce the
evidence. `runtime_snapshot` records the relevant catalog/provider versions,
availability, bounds, and license or environment constraints. Do not turn
unknown fields into positive claims: put them in `open_obligations`.

Use statuses consistently:

- `accepted`: ready for the named next stage;
- `needs_revision`: the work is in scope but missing evidence or has a contract
  defect;
- `rejected`: a candidate gate or mathematical obligation failed;
- `blocked`: an external runtime, authorization, or source dependency prevented
  progress; and
- `complete`: the stage finished and its evidence is ready for downstream use.

Every non-accepted handoff names `missing_evidence` or the failed obligation,
the supporting evidence, and a concrete `next_action`. A later stage must
return an incomplete handoff rather than silently repairing the earlier stage.

## Stage-specific contents

Keep the common envelope stable and add only the fields specific to the stage:

| Stage | Minimum stage-specific contents |
| --- | --- |
| Discovery | move episodes, candidate-gate results, portfolio delta, public reproduction, and evaluation hypothesis |
| Implementation | exact outcome and artifact relationships, failure semantics, validation run, compatibility, and control/treatment delta |
| Checker | exact claim, obligation ledger, certificate bindings, producer/checker dependency comparison, authorization scope, and attack evidence |
| Evaluation | frozen comparison, case/oracle provenance, correctness and false-certification results, contamination/proof gaps, and portfolio decision |

## Reproducibility

For comparative evaluation, bind the handoff to the git tree, visible case
bundle, catalog availability, provider/runtime, model/settings, prompt, oracle,
and scorer identities. Record seeds where available and state when provider
sampling is not deterministic. A version string without the corresponding
content or availability digest is not an adequate snapshot for replay.
