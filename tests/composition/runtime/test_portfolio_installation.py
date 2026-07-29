from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

from jacobian.portfolio import assembler
from jacobian.portfolio.result import PortfolioInstallation


class _RecordingContext:
    def __init__(self, events: list[str], name: str) -> None:
        self.events = events
        self.name = name

    def __enter__(self) -> None:
        self.events.append(f"enter:{self.name}")

    def __exit__(self, *_exc: object) -> None:
        self.events.append(f"exit:{self.name}")


def test_install_portfolio_owns_transaction_and_phase_order(monkeypatch) -> None:
    events: list[str] = []
    store = SimpleNamespace(
        transaction=lambda: _RecordingContext(events, "store"),
    )
    checkers = SimpleNamespace(
        policy_transaction=lambda: _RecordingContext(events, "policy"),
    )
    core = SimpleNamespace(store=store, checkers=checkers)
    application = SimpleNamespace(core=core)
    context = SimpleNamespace(store=store)

    class Resolver:
        def __init__(self) -> None:
            events.append("resolver:init")

        def resolve(self):
            events.append("resolver:resolve")
            return "runtimes"

    class Foundation:
        def __init__(self, _context) -> None:
            events.append("foundation:init")

        def install(self, _core, _result, _runtimes) -> None:
            events.append("foundation:install")

    class Core:
        def __init__(self, _context) -> None:
            events.append("core:init")

        def install(self, _application, _result) -> None:
            events.append("core:install")

    class Resource:
        def __init__(self, _context) -> None:
            events.append("resource:init")

        def install(self, _result) -> None:
            events.append("resource:install")

    class Reference:
        def __init__(self, _context, _resolver) -> None:
            events.append("reference:init")

        def install(self, _application, _result, *, capability_adapter_entrypoints):
            events.append(f"reference:install:{capability_adapter_entrypoints}")

    monkeypatch.setattr(assembler, "ProviderAvailabilityResolver", Resolver)
    monkeypatch.setattr(assembler, "FoundationInstaller", Foundation)
    monkeypatch.setattr(assembler, "CoreApplicationInstaller", Core)
    monkeypatch.setattr(assembler, "ResourceCapabilityInstaller", Resource)
    monkeypatch.setattr(assembler, "ReferenceLeanInstaller", Reference)
    monkeypatch.setattr(assembler, "cached_package_digests", lambda: nullcontext())

    result = assembler.install_portfolio(
        context,
        application,
        capability_adapter_entrypoints=("fixture:adapter",),
    )

    assert isinstance(result, PortfolioInstallation)
    assert events == [
        "resolver:init",
        "enter:policy",
        "enter:store",
        "resolver:resolve",
        "foundation:init",
        "foundation:install",
        "core:init",
        "core:install",
        "resource:init",
        "resource:install",
        "reference:init",
        "reference:install:('fixture:adapter',)",
        "exit:store",
        "exit:policy",
    ]
