from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from jacobian.capabilities import CapabilityInvocationError
from jacobian.contracts.capabilities import (
    CapabilityInstallTier,
    CapabilityMode,
    CapabilityProviderAvailability,
    CapabilityProviderDigestKind,
    CapabilityProviderRuntime,
    CapabilityRequest,
)
from jacobian.contracts.lean import LeanEnvironment
from jacobian.lean_exploration import LeanProofStateAdapter, _Resources


def test_typed_goal_extraction_failure_is_a_structured_non_conclusion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = CapabilityProviderRuntime(
        provider="jacobian.lean4",
        availability=CapabilityProviderAvailability.AVAILABLE,
        version="1",
        digest="sha256:" + "a" * 64,
        digest_kind=CapabilityProviderDigestKind.SOURCE_TREE,
        platform="any",
        install_tier=CapabilityInstallTier.T0,
        license_id="MIT",
    )
    installation = SimpleNamespace(
        lean_version="4.31.0",
        lean_commit="abc",
        mathlib_commit=None,
    )
    resources = cast(
        _Resources,
        SimpleNamespace(
            installations={LeanEnvironment.CORE: installation},
            provider_runtime=runtime,
            repl=SimpleNamespace(
                execute_clean=lambda **_: (
                    {"sorries": [{"proofState": 0}]},
                    {"proofState": 0, "goals": ["⊢ True"]},
                    {
                        "proofState": 1,
                        "goals": ["⊢ True"],
                        "proofStatus": "InProgress",
                    },
                )
            ),
        ),
    )

    def fail_extraction(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("helper protocol failed")

    monkeypatch.setattr(
        "jacobian.lean_exploration._extract_typed_goals",
        fail_extraction,
    )

    with pytest.raises(CapabilityInvocationError) as error:
        LeanProofStateAdapter(resources).invoke(
            CapabilityRequest(
                capability_id="lean.proof_state.apply_tactic",
                mode=CapabilityMode.EXPLORE,
                input={"statement": "True", "tactic": "skip"},
            )
        )

    assert error.value.diagnostic.code == "LEAN_PROOF_STATE_EXTRACTION_FAILED"
    assert error.value.diagnostic.stage == "proof_state_extraction"
