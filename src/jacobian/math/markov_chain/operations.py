"""Markov chain operations backed by SymPy."""

from __future__ import annotations

from jacobian.canonical import parse_canonical_integer

__all__ = [
    "ergodic_properties",
    "stationary_distribution",
    "stationary_distribution_extremes",
]


def stationary_distribution_extremes(matrix):  # type: ignore[no-untyped-def]
    """Return one normalized stationary vector for every closed class."""

    import networkx as nx
    import sympy

    n = len(matrix)
    p = sympy.Matrix(
        [
            [
                sympy.Rational(
                    parse_canonical_integer(matrix[i][j]["num"]),
                    parse_canonical_integer(matrix[i][j]["den"]),
                )
                for j in range(n)
            ]
            for i in range(n)
        ]
    )
    graph: nx.DiGraph[int] = nx.DiGraph()
    graph.add_nodes_from(range(n))
    graph.add_edges_from(
        (source, target)
        for source, row in enumerate(matrix)
        for target, value in enumerate(row)
        if value["num"] != "0"
    )
    closed_classes = sorted(
        (
            tuple(sorted(component))
            for component in nx.strongly_connected_components(graph)
            if not any(
                target not in component
                for source in component
                for target in graph.successors(source)
            )
        ),
        key=lambda component: component,
    )
    extremes = []
    for closed_class in closed_classes:
        submatrix = p.extract(closed_class, closed_class)
        equations = submatrix.T - sympy.eye(len(closed_class))
        equations[len(closed_class) - 1, :] = sympy.ones(1, len(closed_class))
        rhs = sympy.zeros(len(closed_class), 1)
        rhs[len(closed_class) - 1, 0] = 1
        local = equations.inv() * rhs
        distribution = [sympy.S.Zero] * n
        for index, state in enumerate(closed_class):
            distribution[state] = local[index]
        extremes.append((closed_class, distribution))
    return extremes


def stationary_distribution(matrix):  # type: ignore[no-untyped-def]
    """Return the unique stationary distribution, rejecting non-unique chains."""

    extremes = stationary_distribution_extremes(matrix)  # type: ignore[no-untyped-call]
    if len(extremes) != 1:
        raise ValueError(
            "the Markov chain does not have a unique stationary distribution"
        )
    return extremes[0][1]


def ergodic_properties(matrix):  # type: ignore[no-untyped-def]
    import networkx as nx

    graph: nx.DiGraph[int] = nx.DiGraph()
    graph.add_nodes_from(range(len(matrix)))
    graph.add_edges_from(
        (source, target)
        for source, row in enumerate(matrix)
        for target, value in enumerate(row)
        if value["num"] != "0"
    )
    irreducible = nx.is_strongly_connected(graph)
    aperiodic = all(
        nx.is_aperiodic(graph.subgraph(component))
        for component in nx.strongly_connected_components(graph)
    )
    return irreducible, aperiodic
