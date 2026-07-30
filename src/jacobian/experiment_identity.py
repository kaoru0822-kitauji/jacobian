"""Opaque identities shared by durable experiment services."""

from __future__ import annotations

import uuid


def new_experiment_uri() -> str:
    """Return a new opaque experiment identity."""

    return f"experiment://{uuid.uuid4().hex}"
