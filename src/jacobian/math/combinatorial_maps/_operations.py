"""Domain adapter for combinatorial-map operations."""

from __future__ import annotations

from jacobian.math.combinatorial_maps._models import (
    ConnectedComponentsRequest,
    ConnectedComponentsResult,
    DualRequest,
    DualResult,
    EulerCharacteristicRequest,
    EulerCharacteristicResult,
    FacesRequest,
    FacesResult,
    OrientableGenusRequest,
    OrientableGenusResult,
    OrientationReverseRequest,
    OrientationReverseResult,
    VertexFaceIncidenceRequest,
    VertexFaceIncidenceResult,
)
from jacobian.math.combinatorial_maps.operations import (
    connected_components,
    dual_map,
    euler_characteristic,
    face_orbits,
    orientable_genus,
    orientation_reverse,
    vertex_face_incidence,
)

__all__ = [
    "compute_connected_components",
    "compute_dual",
    "compute_euler_characteristic",
    "compute_faces",
    "compute_orientable_genus",
    "compute_orientation_reverse",
    "compute_vertex_face_incidence",
]


def compute_faces(request: FacesRequest) -> FacesResult:
    walks, face_of_dart, successor, _ = face_orbits(request.map)
    n = len(request.map.darts)
    return FacesResult._from_kernel(
        request,
        face_walks=tuple(tuple(walk) for walk in walks),
        face_of_dart=tuple(face_of_dart[d] for d in range(n)),
        successor=tuple(successor),
    )


def compute_euler_characteristic(
    request: EulerCharacteristicRequest,
) -> EulerCharacteristicResult:
    per_component, total = euler_characteristic(request.map)
    return EulerCharacteristicResult._from_kernel(
        per_component=tuple(
            {"V": row["V"], "E": row["E"], "F": row["F"], "chi": row["chi"]}
            for row in per_component
        ),
        total={
            "V": total["V"],
            "E": total["E"],
            "F": total["F"],
            "chi": total["chi"],
        },
    )


def compute_orientable_genus(
    request: OrientableGenusRequest,
) -> OrientableGenusResult:
    per_component, total = orientable_genus(request.map)
    return OrientableGenusResult._from_kernel(
        per_component=tuple(per_component),
        total=total,
    )


def compute_orientation_reverse(
    request: OrientationReverseRequest,
) -> OrientationReverseResult:
    reversed_map, bijection = orientation_reverse(request.map)
    return OrientationReverseResult._from_kernel(
        request,
        reversed_map=reversed_map,
        face_bijection=bijection,
    )


def compute_connected_components(
    request: ConnectedComponentsRequest,
) -> ConnectedComponentsResult:
    vertex_component, dart_component, face_component = connected_components(request.map)
    n_vertices = request.map.vertex_count
    n_darts = len(request.map.darts)
    walks, _, _, _ = face_orbits(request.map)
    n_faces = len(walks)
    return ConnectedComponentsResult._from_kernel(
        vertex_component=tuple(vertex_component[v] for v in range(n_vertices)),
        dart_component=tuple(dart_component[d] for d in range(n_darts)),
        face_component=tuple(face_component[f] for f in range(n_faces)),
    )


def compute_dual(request: DualRequest) -> DualResult:
    dual, primal_to_dual = dual_map(request.map)
    return DualResult._from_kernel(dual=dual, primal_to_dual=primal_to_dual)


def compute_vertex_face_incidence(
    request: VertexFaceIncidenceRequest,
) -> VertexFaceIncidenceResult:
    multiplicity, boolean = vertex_face_incidence(request.map)
    nested: dict[int, dict[int, int]] = {}
    for (vertex, face), count in multiplicity.items():
        nested.setdefault(vertex, {})[face] = count
    boolean_incidence = {v: tuple(sorted(boolean[v])) for v in sorted(boolean)}
    return VertexFaceIncidenceResult._from_kernel(
        multiplicity=nested,
        boolean_incidence=boolean_incidence,
    )
