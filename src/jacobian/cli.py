"""Typer command-line adapter for the v0.2 kernel."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer

from jacobian.canonical import loads_strict_json
from jacobian.contracts.conjectures import (
    ConjectureOperation,
    ConjectureWorkflowRequest,
)
from jacobian.contracts.discovery import EnumerationBudget, SearchEnumerateRequest
from jacobian.contracts.evaluation import EvaluationProfile
from jacobian.contracts.evidence import WitnessRole
from jacobian.contracts.polytope import PolytopeSeparateRequest
from jacobian.contracts.search import SearchBudget, SearchRunRequest
from jacobian.experiments import ExperimentNotFoundError
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
    _emit(
        reference_catalog(
            state.kernel.references,
            polytope=state.kernel.polytope,
            polytope_checkers=state.kernel.polytope_checkers,
        )
    )


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


@app.command("structure-canonicalize")
def structure_canonicalize(
    context: typer.Context,
    structure_uri: str,
    plugin_id: str,
    wall_seconds: int = 30,
) -> None:
    result = _state(context).kernel.structures.canonicalize(
        structure_uri=structure_uri,
        plugin_id=plugin_id,
        wall_seconds=wall_seconds,
    )
    _emit(result.model_dump(mode="json"))


@app.command("search-enumerate")
def search_enumerate(
    context: typer.Context,
    claim_uri: str,
    plugin_id: str,
    bounds_file: Path,
    quotient_by_isomorphism: bool = False,
    profile: str = "EXACT_CANDIDATE",
    seed: int = 0,
    candidates_max: int = 100_000,
    wall_seconds: int = 300,
    page_size: int = 128,
) -> None:
    experiments = _state(context).kernel.experiments
    handle = experiments.start_enumeration(
        SearchEnumerateRequest(
            claim_uri=claim_uri,
            plugin_id=plugin_id,
            bounds=_read_json_object(bounds_file),
            quotient_by_isomorphism=quotient_by_isomorphism,
            profile=EvaluationProfile(profile),
            seed=seed,
            budget=EnumerationBudget(
                candidates_max=candidates_max,
                wall_seconds=wall_seconds,
                page_size=page_size,
            ),
        )
    )
    result = experiments.wait(
        handle.experiment_uri,
        timeout_seconds=wall_seconds + 5,
    )
    _emit(result.model_dump(mode="json"))


@app.command("search-run")
def search_run(
    context: typer.Context,
    idempotency_key: str,
    claim_uri: str,
    plugin_id: str,
    initial_state_file: Path | None = None,
    profile: str = "EXACT_CANDIDATE",
    seed: int = 0,
    witness_role: str | None = None,
    counterexample_checker_id: str | None = None,
    candidates_max: int = 100_000,
    iterations_max: int = 10_000,
    wall_seconds: int = 300,
    batch_size: int = 32,
    workers: int = 1,
) -> None:
    """Run an idempotent strategy search; its outputs remain unverified."""

    initial_state = (
        _read_json_object(initial_state_file) if initial_state_file is not None else {}
    )
    search = _state(context).kernel.search
    handle = search.start(
        SearchRunRequest(
            idempotency_key=idempotency_key,
            claim_uri=claim_uri,
            plugin_id=plugin_id,
            initial_state=initial_state,
            profile=EvaluationProfile(profile),
            seed=seed,
            witness_role=(
                WitnessRole(witness_role) if witness_role is not None else None
            ),
            counterexample_checker_id=counterexample_checker_id,
            budget=SearchBudget(
                candidates_max=candidates_max,
                iterations_max=iterations_max,
                wall_seconds=wall_seconds,
                batch_size=batch_size,
                workers=workers,
            ),
        )
    )
    result = search.wait(
        handle.experiment_uri,
        timeout_seconds=wall_seconds + 5,
    )
    _emit(result.model_dump(mode="json"))


@app.command("experiment-inspect")
def experiment_inspect(
    context: typer.Context,
    experiment_uri: str,
) -> None:
    result = _inspect_experiment(_state(context).kernel, experiment_uri)
    _emit(result.model_dump(mode="json"))


@app.command("experiment-wait")
def experiment_wait(
    context: typer.Context,
    experiment_uri: str,
    timeout_seconds: float = 30,
) -> None:
    result = _wait_experiment(
        _state(context).kernel,
        experiment_uri,
        timeout_seconds=timeout_seconds,
    )
    _emit(result.model_dump(mode="json"))


@app.command("experiment-cancel")
def experiment_cancel(
    context: typer.Context,
    experiment_uri: str,
) -> None:
    result = _cancel_experiment(_state(context).kernel, experiment_uri)
    _emit(result.model_dump(mode="json"))


@app.command("experiment-pause")
def experiment_pause(
    context: typer.Context,
    experiment_uri: str,
) -> None:
    result = _state(context).kernel.search.pause(experiment_uri)
    _emit(result.model_dump(mode="json"))


@app.command("experiment-resume")
def experiment_resume(
    context: typer.Context,
    experiment_uri: str,
) -> None:
    search = _state(context).kernel.search
    paused = search.inspect(experiment_uri)
    result = search.resume(experiment_uri)
    if not result.accepted:
        _emit(result.model_dump(mode="json"))
        return
    snapshot = search.wait(
        experiment_uri,
        timeout_seconds=paused.effective_budget.wall_seconds + 5,
    )
    _emit(snapshot.model_dump(mode="json"))


@app.command("conjecture-repair")
def conjecture_repair(
    context: typer.Context,
    source_claim_uri: str,
    verification_record_uri: str,
    plugin_id: str,
    constraints_file: Path | None = None,
    evidence: Annotated[list[str] | None, typer.Option("--evidence")] = None,
    seed: int = 0,
    max_hypotheses: int = 8,
    wall_seconds: int = 60,
) -> None:
    result = _state(context).kernel.conjectures.run(
        ConjectureWorkflowRequest(
            operation=ConjectureOperation.REPAIR,
            plugin_id=plugin_id,
            source_uri=source_claim_uri,
            verification_record_uri=verification_record_uri,
            constraints=(
                _read_json_object(constraints_file)
                if constraints_file is not None
                else {}
            ),
            evidence_uris=tuple(evidence or ()),
            seed=seed,
            max_hypotheses=max_hypotheses,
            wall_seconds=wall_seconds,
        )
    )
    _emit(result.model_dump(mode="json"))


@app.command("conjecture-generate")
def conjecture_generate(
    context: typer.Context,
    plugin_id: str,
    source_uri: str | None = None,
    constraints_file: Path | None = None,
    reference: Annotated[list[str] | None, typer.Option("--reference")] = None,
    evidence: Annotated[list[str] | None, typer.Option("--evidence")] = None,
    seed: int = 0,
    max_hypotheses: int = 8,
    wall_seconds: int = 60,
) -> None:
    result = _state(context).kernel.conjectures.run(
        ConjectureWorkflowRequest(
            operation=ConjectureOperation.GENERATE,
            plugin_id=plugin_id,
            source_uri=source_uri,
            constraints=(
                _read_json_object(constraints_file)
                if constraints_file is not None
                else {}
            ),
            reference_claim_uris=tuple(reference or ()),
            evidence_uris=tuple(evidence or ()),
            seed=seed,
            max_hypotheses=max_hypotheses,
            wall_seconds=wall_seconds,
        )
    )
    _emit(result.model_dump(mode="json"))


@app.command("parameter-generalize")
def parameter_generalize(
    context: typer.Context,
    source_uri: str,
    verification_record_uri: str,
    plugin_id: str,
    constraints_file: Path | None = None,
    evidence: Annotated[list[str] | None, typer.Option("--evidence")] = None,
    seed: int = 0,
    max_hypotheses: int = 8,
    wall_seconds: int = 60,
) -> None:
    result = _state(context).kernel.conjectures.run(
        ConjectureWorkflowRequest(
            operation=ConjectureOperation.PARAMETER_GENERALIZE,
            plugin_id=plugin_id,
            source_uri=source_uri,
            verification_record_uri=verification_record_uri,
            constraints=(
                _read_json_object(constraints_file)
                if constraints_file is not None
                else {}
            ),
            evidence_uris=tuple(evidence or ()),
            seed=seed,
            max_hypotheses=max_hypotheses,
            wall_seconds=wall_seconds,
        )
    )
    _emit(result.model_dump(mode="json"))


@app.command("transform-apply")
def transform_apply(
    context: typer.Context,
    source_uri: str,
    plugin_id: str,
    target_schema_uri: str,
    target_semantics_uri: str,
    requested_relation: str,
    wall_seconds: int = 30,
) -> None:
    result = _state(context).kernel.transformations.apply(
        source_uri=source_uri,
        plugin_id=plugin_id,
        target_schema_uri=target_schema_uri,
        target_semantics_uri=target_semantics_uri,
        requested_relation=requested_relation,
        wall_seconds=wall_seconds,
    )
    _emit(result.model_dump(mode="json"))


@app.command("transform-verify")
def transform_verify(
    context: typer.Context,
    transformation_uri: str,
) -> None:
    result = _state(context).kernel.verification.verify_transformation(
        transformation_uri=transformation_uri
    )
    _emit(result.model_dump(mode="json"))


@app.command("polytope-separate")
def polytope_separate(
    context: typer.Context,
    point_uri: str,
    generator_set_uri: str,
    projection: Annotated[list[int] | None, typer.Option("--projection")] = None,
    wall_seconds: int = 30,
) -> None:
    result = _state(context).kernel.polytope.separate(
        PolytopeSeparateRequest(
            point_uri=point_uri,
            generator_set_uri=generator_set_uri,
            projection=tuple(projection) if projection is not None else None,
            wall_seconds=wall_seconds,
        )
    )
    _emit(result.model_dump(mode="json"))


def _state(context: typer.Context) -> CliState:
    state = context.obj
    if not isinstance(state, CliState):
        raise RuntimeError("CLI state was not initialized")
    return state


def _inspect_experiment(
    kernel: JacobianKernel,
    experiment_uri: str,
) -> Any:
    try:
        return kernel.experiments.inspect(experiment_uri)
    except ExperimentNotFoundError:
        return kernel.search.inspect(experiment_uri)


def _wait_experiment(
    kernel: JacobianKernel,
    experiment_uri: str,
    *,
    timeout_seconds: float,
) -> Any:
    try:
        kernel.experiments.inspect(experiment_uri)
    except ExperimentNotFoundError:
        return kernel.search.wait(
            experiment_uri,
            timeout_seconds=timeout_seconds,
        )
    return kernel.experiments.wait(
        experiment_uri,
        timeout_seconds=timeout_seconds,
    )


def _cancel_experiment(
    kernel: JacobianKernel,
    experiment_uri: str,
) -> Any:
    try:
        return kernel.experiments.cancel(experiment_uri)
    except ExperimentNotFoundError:
        return kernel.search.cancel(experiment_uri)


def _read_json(path: Path) -> Any:
    return loads_strict_json(path.read_bytes())


def _read_json_object(path: Path) -> dict[str, Any]:
    value = _read_json(path)
    if not isinstance(value, dict):
        raise typer.BadParameter("JSON input must be an object")
    return value


def _emit(payload: Any) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True))
