# Product model: mathematical tools for AI agents

[Documentation home](../index.md)

- Status: Active product direction
- Scope: Mathematical tools, agent workflows, capability adapters, research
  memory, and optional mathematical assurance
- Compatibility: v0.2 verification records remain valid; this document changes
  the product entry point, not the meaning of `VERIFIED`

## Product definition

Jacobian provides composable mathematical tools for AI agents investigating
conjectures and other mathematically specified problems. Agents use these tools
to search for counterexamples, construct and compare mathematical objects,
compute invariants, decompose proof goals, retrieve premises, develop candidate
proofs, and replay certificates.

Each tool performs a bounded, observable operation and returns typed,
inspectable artifacts with explicit relationships, scope, execution status,
assurance, and provenance. Existing mathematical software and domain plugins
supply mathematical operations; capability adapters expose them through a
common contract. Jacobian provides the composition, artifact, execution, and
assurance layer. Evidence that needs to become a trusted conclusion must be
accepted by an operator-authorized independent checker.

Jacobian's long-term goal is to help agents and human researchers make genuine,
trustworthy progress on open conjectures and other problems that benefit from
executable search and checkable evidence.

The product is the mathematical toolset and its shared capability runtime:
versioned contracts, artifact and provenance storage, execution and budget
control, adapter and plugin boundaries, and optional checker-backed assurance.
MCP is the primary agent-facing interface; the CLI and Python API support local
use and integration without changing the mathematical contracts.

The product succeeds when an agent solves held-out tasks more reliably or
efficiently with Jacobian than the same agent solves them with prompts and a
general-purpose shell alone. Starting an MCP server, calling a tool, or
producing a verification record is necessary infrastructure evidence, not
proof of that product outcome.

## Tool and primitive contract

At the product level these capabilities are tools. Internally, the target
mathematical primitive contract is a versioned capability with one observable
operation. It consumes typed artifacts and returns:

- typed output artifacts;
- explicit relationships to its inputs;
- any proof obligations created by the operation;
- execution status and resource accounting;
- assurance and the evidence supporting it;
- enough provenance to replay or compare the step.

Search, generation, transformation, retrieval, and evaluation primitives may
return useful unverified results. They cannot promote their own output to
verified evidence. Promotion requires an independently authorized checker bound
to the exact claim, semantics, candidate, scope, certificate format, and
checker identity.

Broad actions such as “investigate this conjecture” are workflows, not
primitives. A workflow may coordinate many primitive calls, but it must expose
the stage artifacts and preserve their separate assurance labels. Composite
compatibility tools in the current implementation are convenience façades over
this model, not templates for adding more monolithic tools.

## Ownership model

The boundaries are intentionally narrow:

- The kernel owns artifact identity, execution status, assurance, checker
  authorization, budgets, and provenance.
- Capability adapters connect external SAT, SMT, CAS, optimization, retrieval,
  and proof systems to the primitive contract.
- Domain plugins own mathematical schemas, transformations, invariants,
  witness meanings, and required checker roles.
- Independent checker packages implement replay; operators authorize them.
- Agent workflows and skills own multi-step exploration and proof strategies.
- Reference scenarios and benchmarks own worked examples.

This separation lets a new mathematical operation or external engine appear
behind a capability ID without changing the MCP server or expanding checker
authority.

## System shape

```text
Codex CLI              ChatGPT / remote agent
    │ STDIO                    │ Streamable HTTP
    └──────────────┬───────────┘
                   ▼
          MCP capability projection
          capability://catalog
          capability.describe / capability.invoke
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

The generic capability layer must understand an operation ID, JSON schemas,
supported modes, execution status, assurance, scope, artifact relationships,
proof obligations, and an episode handle. Mathematical semantics remain in
adapters and domain plugins.

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

`CapabilityResult` version 2 exposes a generic operation-specific output plus
first-class scope, completeness, relationships, proof obligations, and artifact
URIs. The shared layer validates artifact bindings and checker-backed lifecycle
states; domain adapters still define the mathematical meaning of relation IDs,
scope parameters, and obligation artifacts.

The [capability workflow evaluation plan](../reference/capability-workflow-evaluations.md)
defines the first four held-out workflows and the evidence required before
adding more capability IDs.

Deploy an operator-approved adapter package with a repeatable
`--capability-adapter package.module:factory` option. The factory receives the
tenant's `JacobianKernel` and returns a `CapabilityAdapter`. Loading Python code
is an operator action, never a model tool; it establishes availability, not
mathematical trust.

The initial bundled catalog contains:

- `graph.search.atlas` for bounded exact-order construction from NetworkX's
  maintained Graph Atlas;
- `graph.compute.properties` for exact batched properties over Jacobian graph
  artifacts;
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

Every operationally completed, reusable capability invocation is stored as an
immutable research episode and indexed locally. Invalid requests,
infrastructure errors, timeouts, and cancellations are returned with their
operational status but do not enter research memory. An episode binds:

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
advertises one read-only discovery tool and one extensible invocation tool
rather than every backend operation.

Remote hosts use Streamable HTTP and subject-bound tenant state. Authentication,
tenant isolation, persistence, and TLS are deployment responsibilities, not
mathematical primitives. See
[Deploy the remote MCP server](../how-to/deploy-remote-mcp.md) and the
[threat model](threat-model.md) for their concrete requirements.

## Product evidence

The immediate product work is to stabilize the primitive contract, make stage
composition visible, and exercise external adapters without kernel or MCP
edits. Authenticated hosting, local research memory, and compact tool
projection support that work; they are not substitutes for useful mathematical
operations.

Agent evaluations should measure held-out mathematical tasks, including
counterexample search, claim transformation, proof decomposition, premise
retrieval, and independent replay. Cross-project corpus providers should follow
only after local episode queries are empirically useful. The
[agent evaluation protocol](../reference/agent-evaluations.md) defines the
controls, retained evidence, and scoring required for a product claim.

## Non-goals

- A universal `solve_conjecture` endpoint
- Reimplementing Lean, Alloy, SAT/SMT, CAS, or optimization engines
- Treating a caller's self-review as independent verification
- Requiring verification for every computation or retrieval
- Letting a database entry become true because it is popular or highly ranked
- Claiming process isolation from a Python child process or bearer token alone
