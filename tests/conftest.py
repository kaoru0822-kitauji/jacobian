"""Suite-wide pytest conventions."""

import shutil
from pathlib import Path

import pytest

_LAYER_MARKERS = {
    "integration": pytest.mark.integration,
    "end_to_end": pytest.mark.end_to_end,
}


@pytest.fixture(scope="session")
def kernel_store_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build immutable core descriptors once per pytest worker."""

    from jacobian.kernel import JacobianKernel

    template = tmp_path_factory.mktemp("kernel-store-template")
    kernel = JacobianKernel(template)
    del kernel
    return template


@pytest.fixture
def initialized_kernel_store(
    tmp_path: Path,
    kernel_store_template: Path,
) -> None:
    """Seed an isolated test root with the process's core descriptor snapshot."""

    shutil.copytree(kernel_store_template, tmp_path, dirs_exist_ok=True)


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
