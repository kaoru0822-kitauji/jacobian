"""Pure reward calculation shared by generated verifier fixtures and tests."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RewardDimensions:
    correctness: float
    evidence_validity: float
    scope_accuracy: float
    assurance_calibration: float

    def aggregate(self, *, false_certification: bool = False) -> float:
        values = (
            self.correctness,
            self.evidence_validity,
            self.scope_accuracy,
            self.assurance_calibration,
        )
        if any(value < 0 or value > 1 for value in values):
            raise ValueError("reward dimensions must be in [0, 1]")
        if self.correctness == 0 or false_certification:
            return 0.0
        return (
            0.7 * self.correctness
            + 0.1 * self.evidence_validity
            + 0.1 * self.scope_accuracy
            + 0.1 * self.assurance_calibration
        )
