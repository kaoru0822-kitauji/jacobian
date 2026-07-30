"""Graph construction, property, coloring, composition, and shrinking capabilities."""

from jacobian.graphs.capabilities import GraphInstallation, install_graph_capabilities
from jacobian.graphs.coloring import (
    GraphColoringInstallation,
    install_graph_coloring_capabilities,
)
from jacobian.graphs.composition import (
    GraphCompositionInstallation,
    install_graph_composition_capabilities,
)
from jacobian.graphs.isomorphism import (
    GraphIsomorphismInstallation,
    install_graph_isomorphism,
)
from jacobian.graphs.shrinking import (
    GraphShrinkingInstallation,
    install_graph_shrinking,
)

__all__ = [
    "GraphColoringInstallation",
    "GraphCompositionInstallation",
    "GraphInstallation",
    "GraphIsomorphismInstallation",
    "GraphShrinkingInstallation",
    "install_graph_capabilities",
    "install_graph_coloring_capabilities",
    "install_graph_composition_capabilities",
    "install_graph_isomorphism",
    "install_graph_shrinking",
]
