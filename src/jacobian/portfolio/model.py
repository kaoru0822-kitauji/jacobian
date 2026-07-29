"""Typed declaration of installed domain-owned bundles."""

from __future__ import annotations

from dataclasses import dataclass

from jacobian.operations import DomainBundle


@dataclass(frozen=True, slots=True)
class PortfolioPlan:
    """Explicit, ordered built-in portfolio without dynamic discovery.

    The plan is a literal, ordered tuple of domain-owned ``DomainBundle``
    installation units. It performs no discovery, registration, or ranking:
    callers install it through
    :class:`jacobian.portfolio.domain_installation.DomainBundleInstaller`,
    which records every per-bundle outcome as a typed diagnostic.
    """

    domain_bundles: tuple[DomainBundle, ...]

    def validate(self) -> None:
        """Reject structural portfolio defects before installation.

        Plan-level defects (non-bundles, blank domain IDs, duplicate domains)
        are programming errors and fail fast. Installation failures other than
        declared provider unavailability also propagate from the assembler.
        """

        domain_ids: list[str] = []
        for bundle in self.domain_bundles:
            if not isinstance(bundle, DomainBundle):
                raise TypeError(
                    "portfolio domain bundles must be DomainBundle instances, "
                    f"not {type(bundle).__name__}"
                )
            if not bundle.domain_id:
                raise ValueError("portfolio contains a bundle with a blank domain id")
            domain_ids.append(bundle.domain_id)
        duplicates = sorted(
            domain_id
            for domain_id in set(domain_ids)
            if domain_ids.count(domain_id) > 1
        )
        if duplicates:
            raise ValueError(
                "portfolio contains duplicate domain bundles: " + ", ".join(duplicates)
            )

    @property
    def domain_ids(self) -> tuple[str, ...]:
        """The ordered domain IDs declared by this plan."""

        return tuple(bundle.domain_id for bundle in self.domain_bundles)

    def bundle_for(self, domain_id: str) -> DomainBundle | None:
        """Return the bundle declared for ``domain_id``, or ``None`` if absent."""

        for bundle in self.domain_bundles:
            if bundle.domain_id == domain_id:
                return bundle
        return None
