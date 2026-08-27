from __future__ import annotations

from collections.abc import Mapping

import pytest
from benchmarks.tooling.harbor_proxy import render_config


def _mapping(value: object) -> Mapping[str, object]:
    assert isinstance(value, Mapping)
    return value


def _sequence(value: object) -> list[object]:
    assert isinstance(value, list)
    return value


def test_render_config_chains_transparent_egress_through_http_proxy() -> None:
    config = _mapping(render_config("http://docker-host:7890"))

    services = _sequence(config["services"])
    transparent_service = _mapping(services[0])
    explicit_service = _mapping(services[1])
    chains = _sequence(config["chains"])
    chain = _mapping(chains[0])
    hops = _sequence(chain["hops"])
    hop = _mapping(hops[0])
    nodes = _sequence(hop["nodes"])
    node = _mapping(nodes[0])
    transparent_handler = _mapping(transparent_service["handler"])
    assert transparent_handler["chain"] == "upstream-proxy"
    assert transparent_service["bypass"] == "allowlist"
    assert transparent_service["sockopts"] == {"mark": 114514}
    assert explicit_service == {
        "name": "explicit-egress",
        "addr": "127.0.0.1:12346",
        "bypass": "allowlist",
        "handler": {"type": "http", "chain": "upstream-proxy"},
        "listener": {"type": "tcp"},
    }
    assert hop["bypass"] == "direct-private"
    assert hop["sockopts"] == {"mark": 114514}
    assert node["addr"] == "docker-host:7890"
    assert node["connector"] == {"type": "http"}
    bypasses = _sequence(config["bypasses"])
    direct_private = _mapping(bypasses[1])
    assert direct_private["matchers"] == [
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "169.254.0.0/16",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    ]


def test_render_config_rejects_unsupported_proxy_scheme() -> None:
    with pytest.raises(ValueError, match="upstream proxy must use"):
        render_config("https://docker-host:7890")
