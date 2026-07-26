"""Suite-wide pytest conventions."""

from pathlib import Path

import pytest

_LAYER_MARKERS = {
    "integration": pytest.mark.integration,
    "end_to_end": pytest.mark.end_to_end,
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Keep layer markers aligned with the suite's directory structure."""

    tests_root = Path(__file__).parent
    for item in items:
        try:
            layer = Path(item.path).relative_to(tests_root).parts[0]
        except (ValueError, IndexError):
            continue
        marker = _LAYER_MARKERS.get(layer)
        if marker is not None:
            item.add_marker(marker)
