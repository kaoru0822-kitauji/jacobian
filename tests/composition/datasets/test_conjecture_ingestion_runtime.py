from pathlib import Path

from jacobian.runtime import create_runtime


def test_runtime_exposes_typed_conjecture_ingestion_installation(
    tmp_path: Path,
) -> None:
    with create_runtime(tmp_path) as runtime:
        installation = runtime.portfolio.conjecture_ingestion
        bundle = runtime.portfolio.domain_bundles["conjecture_ingestion"]

        assert installation is not None
        assert installation.semantics_uri == bundle.semantics_uri
        assert (
            installation.artifact_schema_uri
            == bundle.result_schema_uris["dataset.conjecture.ingest"]
        )
