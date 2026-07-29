# Graph distance matrix

[Documentation home](../index.md)

`graph.distance_matrix.compute` returns one complete matrix of exact
unweighted shortest-path distances for a bounded finite simple undirected
graph. The producer uses the existing `GraphInvariantRequest` graph contract,
so inputs retain the established limit of 32 vertices and 496 edges.

## Result semantics

The result is bound to
`unweighted-shortest-path-distance-matrix.v1` and makes its representation
choices explicit:

- `vertices` is the complete input vertex set in lexicographic ascending order;
- `distances[i][j]` covers every ordered pair of vertices in that order;
- a finite entry is the number of edges in a shortest path;
- an unreachable pair is represented by JSON `null`, never a numeric sentinel;
- the diagonal is zero, finite off-diagonal entries are positive, and the
  matrix is symmetric; and
- `connected` is true exactly when the graph is nonempty and every matrix
  entry is finite.

The empty graph returns an empty matrix with `connected = false`. A singleton
returns `[[0]]` with `connected = true`.

The result model rejects inconsistent ordering, shape, diagonal, symmetry,
component closure, triangle inequality, or connectedness before an artifact is
written.

## Scope and composition

This capability exposes the distance matrix as one inspectable mathematical
outcome. It does not compute a diameter, radius, vertex eccentricity, distance
between derived vertex sets, or a conjecture-specific inequality. An agent can
derive such quantities by composing this artifact with independently obtained
sets or other capabilities.

The producer is capped at `COMPUTED`. That assurance means the bounded
operation completed and produced a typed artifact; it is not independent
verification of the distance claim.
