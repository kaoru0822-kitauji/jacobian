# Graph counterexample shrinking

[Documentation home](../index.md)

`graph.counterexample.shrink` is a bounded exploration capability for finite
simple undirected graphs. Version 1 supports the registered
`graph.property.non_bipartite` property and two deterministic reducers:

- `delete_vertex`, which removes one vertex and every incident edge;
- `delete_edge`, which removes one edge.

The adapter delegates proposal search to the generic `shrink.run` service.
The graph reducer is therefore an untrusted proposal source. Every accepted
reduction must be replayed by the operator-selected active preservation
checker compatible with the graph schema, semantics, property-claim schema,
and `graph.property.non_bipartite.preservation` format.

## Result and trace

The result records every attempted reduction in execution order. Each attempt
identifies the source graph, proposed graph, exact deleted vertex or edge,
candidate digest, outcome, and—only for accepted steps—the independent
verification record. The local-minimality scope also records the expected and
completed attempt counts, completeness status, and remaining obligations.
Possible outcomes distinguish verified acceptance, mathematical property
rejection, checker failure, and invalid reduction.

The trace is an immutable artifact bound to the initial graph, final graph,
property claim, all proposed graph artifacts, and accepted-step verification
records.

## Minimality boundary

Version 1 reports only the tested single-deletion neighborhood of the final
graph. It sets `one_step_locally_minimal` only when:

1. the final graph itself was accepted by the property checker;
2. every requested single vertex or edge deletion was attempted exactly once;
3. every such deletion was mathematically rejected by the checker; and
4. execution completed without a timeout, checker error, invalid proposal, or
   budget omission.

An incomplete enumeration, cancellation, unavailable checker, or worker error
leaves minimality unknown. This evidence is local to the declared reducer
family; it does not imply global minimality.

The result separately lists tested and untested deletions. It never claims
global minimality. Restricting the reducer set restricts the meaning of the
local-minimality result to that declared reducer set.
