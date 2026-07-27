from __future__ import annotations

import pytest
from pydantic import ValidationError

import jacobian.contracts.sat as sat_contracts
from jacobian.contracts.sat import SatLratVerificationRequest


def test_lrat_request_rejects_oversized_encoding_before_decoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_decode(_: str) -> bytes:
        raise AssertionError("oversized proof was decoded")

    monkeypatch.setattr(sat_contracts, "_decode_base64", unexpected_decode)

    with pytest.raises(ValidationError, match="exceeds max_proof_bytes"):
        SatLratVerificationRequest(
            cnf_uri="artifact://sha256/" + "a" * 64,
            proof_base64="AAAAAAAA",
            limits={"max_proof_bytes": 1},
        )
