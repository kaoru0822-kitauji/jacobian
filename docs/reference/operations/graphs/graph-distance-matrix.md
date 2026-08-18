# Graph metric operations

[Documentation home](../../../index.md) · [Tool surface](../../tools.md)

Jacobian exposes the complete bounded distance matrix of a typed finite graph.
`graph.distance_matrix.compute` returns all pairwise distances or a typed
non-applicability outcome for a disconnected graph.

Radius and diameter are cheap projections of the complete matrix, so they are
retained as `jacobian.math.graphs.radius` and
`jacobian.math.graphs.diameter`. Pass the graph itself to the public operation;
there is no graph handle or stored graph value.
