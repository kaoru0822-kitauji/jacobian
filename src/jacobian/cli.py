"""Typer command-line adapter for the v0.1 kernel."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer

from jacobian.canonical import loads_strict_json
from jacobian.kernel import JacobianKernel
from jacobian.references import reference_catalog

app = typer.Typer(
    name="jacobian",
    help="Verifier-centric workbench for bounded executable mathematics.",
    no_args_is_help=True,
)


class CliState:
    def __init__(self, kernel: JacobianKernel) -> None:
        self.kernel = kernel


@app.callback()
def configure(
    context: typer.Context,
    state_dir: Annotated[
        Path,
        typer.Option(
            "--state-dir",
            help="Local artifact and metadata directory.",
        ),
    ] = Path(".jacobian"),
    install_references: Annotated[
        bool,
        typer.Option(
            "--install-references/--no-install-references",
            help="Install bundled graph/path and matrix reference domains.",
        ),
    ] = True,
) -> None:
    context.obj = CliState(
        JacobianKernel(
            state_dir,
            install_references=install_references,
        )
    )


@app.command("init")
def initialize(context: typer.Context) -> None:
    """Initialize storage and print installed reference identifiers."""

    state = _state(context)
    _emit(reference_catalog(state.kernel.references))


@app.command("artifact-put")
def artifact_put(
    context: typer.Context,
    schema_uri: str,
    semantics_uri: str,
    payload_file: Path,
    parent: Annotated[list[str] | None, typer.Option("--parent")] = None,
    summary: str = "",
) -> None:
    payload = _read_json(payload_file)
    result = _state(context).kernel.artifacts.put(
        schema_uri=schema_uri,
        semantics_uri=semantics_uri,
        payload=payload,
        parents=tuple(parent or ()),
        summary=summary,
    )
    _emit(result.model_dump(mode="json"))


@app.command("claim-validate")
def claim_validate(
    context: typer.Context,
    claim_uri: str,
    plugin_id: str,
) -> None:
    result = _state(context).kernel.claims.validate(
        claim_uri=claim_uri,
        plugin_id=plugin_id,
    )
    _emit(result.model_dump(mode="json"))


@app.command("evaluate-batch")
def evaluate_batch(
    context: typer.Context,
    claim_uri: str,
    plugin_id: str,
    candidate_uri: Annotated[list[str], typer.Option("--candidate-uri")],
    profile: str = "FAST",
    seed: int = 0,
    wall_seconds: int = 60,
) -> None:
    result = _state(context).kernel.evaluation.evaluate_batch(
        claim_uri=claim_uri,
        candidate_uris=tuple(candidate_uri),
        plugin_id=plugin_id,
        profile=profile,
        seed=seed,
        wall_seconds=wall_seconds,
    )
    _emit(result.model_dump(mode="json"))


@app.command("witness-find")
def witness_find(
    context: typer.Context,
    claim_uri: str,
    candidate_uri: str,
    plugin_id: str,
    witness_role: str = "DEFEATS_CANDIDATE",
    wall_seconds: int = 300,
) -> None:
    result = _state(context).kernel.witnesses.find(
        claim_uri=claim_uri,
        candidate_uri=candidate_uri,
        plugin_id=plugin_id,
        witness_role=witness_role,
        wall_seconds=wall_seconds,
    )
    _emit(result.model_dump(mode="json"))


@app.command("witness-verify")
def witness_verify(
    context: typer.Context,
    claim_uri: str,
    candidate_uri: str,
    witness_uri: str,
    checker_id: str,
) -> None:
    result = _state(context).kernel.verification.verify_witness(
        claim_uri=claim_uri,
        candidate_uri=candidate_uri,
        witness_uri=witness_uri,
        checker_id=checker_id,
    )
    _emit(result.model_dump(mode="json"))


@app.command("certificate-verify")
def certificate_verify(
    context: typer.Context,
    certificate_uri: str,
) -> None:
    result = _state(context).kernel.verification.verify_certificate(
        certificate_uri=certificate_uri
    )
    _emit(result.model_dump(mode="json"))


@app.command("shrink-run")
def shrink_run(
    context: typer.Context,
    target_kind: str,
    target_uri: str,
    claim_uri: str,
    plugin_id: str,
    preservation_checker_id: str,
    reducer: Annotated[list[str], typer.Option("--reducer")],
    objective: Annotated[list[str] | None, typer.Option("--objective")] = None,
    evaluations: int = 10_000,
) -> None:
    result = _state(context).kernel.shrinking.run(
        target_kind=target_kind,
        target_uri=target_uri,
        claim_uri=claim_uri,
        plugin_id=plugin_id,
        preservation_checker_id=preservation_checker_id,
        reducers=tuple(reducer),
        objectives=tuple(objective or ()),
        evaluation_budget=evaluations,
    )
    _emit(result.model_dump(mode="json"))


def _state(context: typer.Context) -> CliState:
    state = context.obj
    if not isinstance(state, CliState):
        raise RuntimeError("CLI state was not initialized")
    return state


def _read_json(path: Path) -> Any:
    return loads_strict_json(path.read_bytes())


def _emit(payload: Any) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True))
