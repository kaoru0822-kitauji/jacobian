"""Lazy provider loaders for the graph-optimization domain.

The z3 solver module is shared across :mod:`exact_search`, :mod:`invariants`,
and :mod:`operations`.  A single :class:`~jacobian.providers.LazyLoader` owns
that boundary so the domain does not grow duplicate hand-rolled loader helpers.
The loader defers the import until first invocation, caches success and failure,
and keeps bundle/catalog construction free of heavy solver imports.
"""

from __future__ import annotations

import importlib
from typing import Any

from jacobian.providers import LazyLoader

Z3_LOADER: LazyLoader[Any] = LazyLoader(
    lambda: importlib.import_module("z3"),
    component_id="jacobian.z3.graph-optimization",
)
