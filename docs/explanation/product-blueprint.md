# Capability-first product blueprint

[Documentation home](../index.md)

- Status: Active product direction
- Scope: Agent-facing MCP, local and remote execution, research memory, and
  optional mathematical assurance
- Compatibility: v0.2 verification records remain valid; this document changes
  the product entry point, not the meaning of `VERIFIED`

## Product definition

Jacobian is an agent-facing mathematical capability and research-memory layer.
It supplies reusable computation, search, solver, formal-proof, retrieval, and
experiment tools so a model can spend more of its context and reasoning budget
on strategy rather than rebuilding infrastructure.

Verification is an available assurance service. It is not a mandatory prelude
to exploration and it is not the only reason to use Jacobian.

The product succeeds when an agent solves held-out tasks more reliably or
efficiently with Jacobian than the same agent solves them with prompts and a
general-purpose shell alone. Starting an MCP server, calling a tool, or
producing a verification record is necessary infrastructure evidence, not
proof of that product outcome.

## Decision rules

Use these rules when adding a feature:

1. Expose a mathematical action, not an internal lifecycle step.
2. Keep large schemas and payloads behind catalogs and resource handles.
3. Let exploration return useful candidates without requiring a `ClaimSpec`.
4. Label every result as heuristic, computed, or verified.
5. Require an authorized local verification record before an adapter may use
   the verified label.
6. Record reusable episodes with provenance and their original assurance.
7. Never turn retrieval rank, solver status, search exhaustion, timeout, or an
   adapter's self-assessment into proof.
8. Add a provider through the capability registry without editing the MCP
   adapter.

## System shape

```text
Codex CLI              ChatGPT / remote agent
    │ STDIO                    │ Streamable HTTP
    └──────────────┬───────────┘
                   ▼
          MCP capability projection
          capability://catalog
          capability.invoke
                   │
                   ▼
             CapabilityService
       ┌───────────┼──────────────┐
       │           │              │
  knowledge     math/solver     experiment
  and memory     adapters        services
       │      Lean SAT SMT CAS       │
       │      Alloy domain tools     │
       └───────────┼─────────────────┘
                   │ optional promotion
                   ▼
        authorized checker / proof engine
                   │
                   ▼
          immutable verification record
```

The generic capability layer understands an operation ID, JSON schemas,
supported modes, execution status, assurance, scope, artifacts, and an episode
handle. Mathematical semantics remain in adapters and domain plugins.

## Capability contract

An adapter registers one `CapabilityDescriptor` and implements:

```python
class CapabilityAdapter(Protocol):
    @property
    def descriptor(self) -> CapabilityDescriptor: ...

    def invoke(self, request: CapabilityRequest) -> CapabilityResult: ...
```

The descriptor declares:

- stable capability ID and version;
- provider and concise model-facing description;
- supported `EXPLORE` and `VERIFY` modes;
- closed input and output JSON Schemas;
- read-only and episode-recording behavior;
- discovery tags.

`CapabilityService` validates both sides of the call, enforces identity and
mode, checks any verified record and its complete parent binding against the
local artifact store, and records the episode. Projected record IDs and
conclusions must agree with the checked record. `MCPServer` does not need a new
tool when an Alloy, Lean, SAT/SMT, CAS, or domain adapter is registered.

Deploy an operator-approved adapter package with a repeatable
`--capability-adapter package.module:factory` option. The factory receives the
tenant's `JacobianKernel` and returns a `CapabilityAdapter`. Loading Python code
is an operator action, never a model tool; it establishes availability, not
mathematical trust.

The initial bundled catalog contains:

- `reference.solve` for bundled reference-domain exploration and verification;
- `lean.check` for checker-backed Lean proof replay;
- `knowledge.search` for trust-labeled local episode retrieval.

These are reference adapters, not a closed ontology.

## Two lanes

### Explore

`EXPLORE` is the default. It may evaluate, search, query memory, call solvers,
generate candidates, or find witnesses. It does not run a checker merely to
make an intermediate result usable.

Explore results use:

- `HEURISTIC` when the result depends on search, an untrusted plugin, a model,
  sampling, or an unchecked witness;
- `COMPUTED` for a deterministic operation whose software contract is tested
  but which does not establish a promoted mathematical claim.

### Verify

`VERIFY` is requested for a durable theorem, counterexample, equivalence,
optimality, exhaustive scope, or reusable database fact. The adapter may invoke
an authorized checker or formal proof engine.

An adapter cannot create verified authority. `CapabilityService` accepts
`VERIFIED` only when the result names a valid local verification-record
artifact and exposes its checked evidence. Failure falls closed to a
non-verified result or operational error.

The lower-level v0.2 verification tools remain available through the `full` and
`verification` MCP profiles for advanced workflows and replay.

## Database-first memory

Every reusable capability invocation is stored as an immutable research
episode and indexed locally. An episode binds:

- capability and adapter version;
- exact request and result;
- exploration or verification mode;
- assurance label and verification record, when present;
- artifact lineage;
- timestamp, summary, and tags.

`knowledge.search` queries the local index. Retrieved records retain their
original assurance; retrieval never upgrades them. The local store is useful
without an external corpus provider.

Later corpus providers add cross-project ranking, temporal cutoffs, review,
retraction, citation, and retention policy. They remain outside checker
authority.

## Local and remote hosts

The local Codex profile uses STDIO and the `capabilities` tool profile. It
advertises one extensible tool rather than every backend operation.

Remote hosts use Streamable HTTP by default. A remote deployment:

- requires an operator-provisioned bearer-token file unless anonymous
  development mode is explicitly selected;
- binds each token to a tenant subject and required scope;
- routes every tool and resource request to a tenant-specific state root;
- hashes tenant IDs before constructing filesystem paths;
- keeps artifact, memory, experiment, plugin, and checker metadata isolated;
- terminates TLS at a trusted reverse proxy or platform ingress;
- mounts the state root and token file as separate persistent volume and
  secret.

Static opaque tokens are an initial deployment mechanism, not a complete
identity platform. Hosted deployments should replace the verifier with their
OAuth/OIDC policy while preserving the tenant subject contract.

## Evaluation

Two benchmark families answer different questions:

- The known-answer MCP pilot checks integration and durable verification.
- The A/B agent benchmark compares the same model on the same task under a
  control condition and a Jacobian capability condition.

The A/B runner must:

- ignore user MCP configuration and construct each condition explicitly;
- fix model, reasoning effort, repository commit, prompt, and budgets;
- randomize or alternate condition order across repetitions;
- retain every transcript and report;
- score mathematical answers with an independent known-answer oracle;
- measure pass rate, false claims, input/output tokens, wall time, tool calls,
  shell calls, and generated files;
- report paired deltas rather than selecting the best run.

One successful MCP transcript does not establish an improvement. A product
claim requires repeated held-out cases with a better correctness/efficiency
frontier and no increase in false certification.

## Delivery order

1. Stabilize capability contracts, local memory, and the two lanes.
2. Keep the compact MCP catalog below the tool-description budget.
3. Exercise at least one external adapter without a kernel or MCP edit.
4. Deploy authenticated Streamable HTTP with tenant-isolation tests.
5. Run paired A/B pilots and use agent feedback to prioritize adapters.
6. Add cross-project corpus providers only after local episode queries are
   empirically useful.

## Non-goals

- A universal `solve_conjecture` endpoint
- Reimplementing Lean, Alloy, SAT/SMT, CAS, or optimization engines
- Treating a caller's self-review as independent verification
- Requiring verification for every computation or retrieval
- Letting a database entry become true because it is popular or highly ranked
- Claiming process isolation from a Python child process or bearer token alone
