from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
INSTALLER = REPOSITORY_ROOT / "deploy" / "install.sh"
SERVICE_STATE = REPOSITORY_ROOT / "deploy" / "lib" / "service_state.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None,
    reason="deploy installer tests require bash",
)


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(INSTALLER), *arguments],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_installer_is_valid_bash() -> None:
    completed = subprocess.run(
        ["bash", "-n", str(INSTALLER)],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_installer_help_exposes_three_deployment_modes() -> None:
    completed = _run("--help")

    assert completed.returncode == 0
    assert "--mode local" in completed.stdout
    assert "--mode domain" in completed.stdout
    assert "--mode tailscale" in completed.stdout
    assert "--install-root" in completed.stdout
    assert "--with-lean" in completed.stdout


def test_lean_dry_run_uses_a_distinct_release_profile() -> None:
    completed = _run("--with-lean", "--dry-run")

    assert completed.returncode == 0, completed.stderr
    release_line = next(
        line
        for line in completed.stdout.splitlines()
        if line.strip().startswith("release:")
    )
    assert release_line.endswith("-lean")
    assert "lean:        pinned CORE + MATHLIB runtime" in completed.stdout


def test_domain_dry_run_reports_connector_without_requiring_root() -> None:
    completed = _run(
        "--mode",
        "domain",
        "--domain",
        "math.example.org",
        "--dry-run",
    )

    assert completed.returncode == 0, completed.stderr
    assert "mode:        domain" in completed.stdout
    assert "connector:   https://math.example.org/mcp" in completed.stdout
    assert "python:      /opt/jacobian/python" in completed.stdout
    assert "caddy:       enabled" in completed.stdout
    assert "funnel:      disabled" in completed.stdout


def test_dry_run_derives_every_runtime_path_from_custom_install_root() -> None:
    completed = _run(
        "--install-root",
        "/srv/math/jacobian",
        "--with-lean",
        "--dry-run",
    )

    assert completed.returncode == 0, completed.stderr
    assert "install:     /srv/math/jacobian" in completed.stdout
    assert "release:     /srv/math/jacobian/releases/" in completed.stdout
    assert "python:      /srv/math/jacobian/python" in completed.stdout


@pytest.mark.parametrize(
    "root",
    (
        "relative/path",
        "/",
        "/srv/path with spaces",
        "/srv/../jacobian",
        "/home/apps/jacobian",
        "/root",
        "/run/user/1000/jacobian",
        "/tmp/jacobian",
        "/var/tmp/jacobian",
    ),
)
def test_install_root_rejects_unsafe_or_ambiguous_paths(root: str) -> None:
    completed = _run("--install-root", root, "--dry-run")

    assert completed.returncode != 0
    assert "--install-root" in completed.stderr


def test_install_root_rejects_an_allowed_symlink_into_a_hidden_path(
    tmp_path: Path,
) -> None:
    shared_memory = Path("/dev/shm")
    if not shared_memory.is_dir() or not os.access(shared_memory, os.W_OK):
        pytest.skip("a writable /dev/shm is required for the symlink sandbox check")
    visible_parent = Path(
        tempfile.mkdtemp(prefix="jacobian-install-root-", dir=shared_memory)
    )
    visible_link = visible_parent / "release-root"
    try:
        visible_link.symlink_to(tmp_path, target_is_directory=True)

        completed = _run(
            "--install-root",
            str(visible_link / "jacobian"),
            "--dry-run",
        )

        assert completed.returncode != 0
        assert "resolves below a path hidden by the systemd sandbox" in completed.stderr
    finally:
        shutil.rmtree(visible_parent)


def test_install_root_canonicalizes_an_allowed_symlink_ancestor() -> None:
    shared_memory = Path("/dev/shm")
    if not shared_memory.is_dir() or not os.access(shared_memory, os.W_OK):
        pytest.skip("a writable /dev/shm is required for the symlink sandbox check")
    visible_parent = Path(
        tempfile.mkdtemp(prefix="jacobian-install-root-", dir=shared_memory)
    )
    actual_root = visible_parent / "actual"
    visible_link = visible_parent / "release-root"
    try:
        actual_root.mkdir()
        visible_link.symlink_to(actual_root, target_is_directory=True)

        completed = _run(
            "--install-root",
            str(visible_link / "jacobian"),
            "--dry-run",
        )

        assert completed.returncode == 0, completed.stderr
        assert f"install:     {actual_root}/jacobian" in completed.stdout
    finally:
        shutil.rmtree(visible_parent)


@pytest.mark.parametrize("target_name", ("actual root", "actual|root"))
def test_install_root_rejects_unsafe_resolved_symlink_targets(
    target_name: str,
) -> None:
    shared_memory = Path("/dev/shm")
    if not shared_memory.is_dir() or not os.access(shared_memory, os.W_OK):
        pytest.skip("a writable /dev/shm is required for the symlink sandbox check")
    visible_parent = Path(
        tempfile.mkdtemp(prefix="jacobian-install-root-", dir=shared_memory)
    )
    actual_root = visible_parent / target_name
    visible_link = visible_parent / "release-root"
    try:
        actual_root.mkdir()
        visible_link.symlink_to(actual_root, target_is_directory=True)

        completed = _run(
            "--install-root",
            str(visible_link / "jacobian"),
            "--dry-run",
        )

        assert completed.returncode != 0
        assert "resolves to a non-root path with unsupported characters" in (
            completed.stderr
        )
    finally:
        shutil.rmtree(visible_parent)


def test_dry_run_never_echoes_supplied_credentials(tmp_path: Path) -> None:
    sentinel = "sentinel-secret-that-must-not-be-logged"
    credentials = tmp_path / "tokens.json"
    credentials.write_text(
        '{"tokens":{"' + sentinel + '":{"tenant_id":"tenant-a"}}}',
        encoding="utf-8",
    )

    completed = _run("--auth-tokens-file", str(credentials), "--dry-run")

    assert completed.returncode == 0, completed.stderr
    assert sentinel not in completed.stdout
    assert sentinel not in completed.stderr


def test_domain_mode_requires_a_valid_fqdn() -> None:
    missing = _run("--mode", "domain", "--dry-run")
    invalid = _run(
        "--mode",
        "domain",
        "--domain",
        "https://math.example.org/path",
        "--dry-run",
    )

    assert missing.returncode != 0
    assert "--mode domain requires --domain" in missing.stderr
    assert invalid.returncode != 0
    assert "fully qualified DNS name" in invalid.stderr


def test_public_anonymous_mode_requires_double_confirmation() -> None:
    rejected = _run(
        "--mode",
        "domain",
        "--domain",
        "math.example.org",
        "--allow-anonymous",
        "--dry-run",
    )
    accepted = _run(
        "--mode",
        "domain",
        "--domain",
        "math.example.org",
        "--allow-anonymous",
        "--confirm-public-anonymous",
        "--dry-run",
    )

    assert rejected.returncode != 0
    assert "--confirm-public-anonymous" in rejected.stderr
    assert accepted.returncode == 0, accepted.stderr
    assert "auth:        anonymous shared tenant jacobian-test" in accepted.stdout


def test_local_mode_rejects_an_unusable_domain_option() -> None:
    completed = _run(
        "--mode",
        "local",
        "--domain",
        "math.example.org",
        "--dry-run",
    )

    assert completed.returncode != 0
    assert "--domain is only valid with --mode domain" in completed.stderr


def test_release_environment_is_built_at_its_final_path() -> None:
    source = INSTALLER.read_text(encoding="utf-8")
    release_block = source[
        source.index('log "installing immutable release') : source.index(
            'log "installing authentication configuration"'
        )
    ]

    assert 'cd "${RELEASE_DIR}"' in release_block
    assert 'UV_PYTHON_INSTALL_DIR="${PYTHON_INSTALL_ROOT}"' in release_block
    assert "--managed-python" in release_block
    assert "--link-mode copy" in release_block
    assert 'mv "${RELEASE_CANDIDATE}" "${RELEASE_DIR}"' not in release_block
    assert '"${FLOCK_BIN}" --nonblock 9' in release_block


def test_release_runtime_is_checked_before_current_symlink_is_changed() -> None:
    source = INSTALLER.read_text(encoding="utf-8")

    validation = source.index('validate_release_runtime "${RELEASE_DIR}"')
    revision_marker = source.index(
        'printf \'%s\\n\' "${REVISION}" >"${RELEASE_DIR}/.git-revision"'
    )
    current_link = source.index('ln -sfn "${RELEASE_DIR}" "${CURRENT_LINK}.new"')

    assert validation < revision_marker < current_link
    assert '"${RUNUSER_BIN}" --user jacobian -- "${entrypoint}" --version' in source


def test_lean_profile_is_built_and_validated_before_activation() -> None:
    source = INSTALLER.read_text(encoding="utf-8")

    install_toolchain = source.index(
        '"${LEAN_ELAN_HOME}/bin/elan" toolchain install "${LEAN_TOOLCHAIN}"'
    )
    inspect_toolchains = source.index('"${LEAN_ELAN_HOME}/bin/elan" toolchain list')
    fetch_cache = source.index("lake exe cache get")
    build_runtime = source.index(
        "lake build repl JacobianLeanRuntime jacobian_lean_proof_state"
    )
    validate = source.index('validate_lean_release_runtime "${RELEASE_DIR}"')
    revision_marker = source.index(
        'printf \'%s\\n\' "${REVISION}" >"${RELEASE_DIR}/.git-revision"'
    )
    current_link = source.index('ln -sfn "${RELEASE_DIR}" "${CURRENT_LINK}.new"')

    assert (
        inspect_toolchains < install_toolchain < fetch_cache < build_runtime < validate
    )
    assert validate < revision_marker < current_link
    assert '"ELAN_HOME=${LEAN_ELAN_HOME}"' in source
    assert '"PATH=${LEAN_SERVICE_PATH}"' in source
    assert 'chmod -R a+rX "${RELEASE_DIR}/lean"' in source
    assert "lean_provider_runtime(" in source
    assert "CapabilityProviderAvailability.AVAILABLE" in source


def test_lean_profile_finds_the_invoking_users_elan_under_sudo() -> None:
    source = INSTALLER.read_text(encoding="utf-8")

    resolve_home = source.index(
        'INVOKING_HOME="$(getent passwd "${SUDO_USER}" | cut -d: -f6 || true)"'
    )
    elan_fallback = source.index('ELAN_FALLBACKS+=("${INVOKING_HOME}/.elan/bin/elan")')
    resolve_elan = source.index('find_executable elan "${ELAN_FALLBACKS[@]}"')

    assert resolve_home < elan_fallback < resolve_elan


def test_systemd_service_can_read_the_operator_managed_lean_toolchain() -> None:
    service = (REPOSITORY_ROOT / "deploy/systemd/jacobian-mcp.service").read_text(
        encoding="utf-8"
    )

    assert "Environment=ELAN_HOME=/opt/jacobian/lean/elan" in service
    assert "Environment=PATH=/opt/jacobian/lean/elan/bin:" in service
    assert "ProtectHome=true" in service


def test_installer_renders_custom_runtime_paths_into_service_and_override() -> None:
    source = INSTALLER.read_text(encoding="utf-8")

    assert '-e "s|/opt/jacobian/current|${CURRENT_LINK}|g"' in source
    assert '-e "s|/opt/jacobian/lean/elan|${LEAN_ELAN_HOME}|g"' in source
    assert source.count('-e "s|/opt/jacobian/current|${CURRENT_LINK}|g"') == 2


def test_lean_profile_requires_catalog_and_behavior_smokes() -> None:
    source = INSTALLER.read_text(encoding="utf-8")
    smoke_block = source[source.index('log "running the read-only deployment smoke"') :]

    for capability_id in (
        "lean.check",
        "lean.proof_state.apply_tactic",
        "lean.term.apply",
        "lean.retrieve.premises",
    ):
        assert f"--require-capability {capability_id}" in smoke_block
    assert '"${RELEASE_DIR}/deploy/smoke_lean.py"' in smoke_block


def test_activation_arms_rollback_before_switching_current() -> None:
    source = INSTALLER.read_text(encoding="utf-8")

    armed = source.index("ROLLBACK_ARMED=1")
    current_link = source.index('ln -sfn "${RELEASE_DIR}" "${CURRENT_LINK}.new"')
    smoke = source.index('log "running the read-only deployment smoke"')
    accepted = source.index("DEPLOYMENT_ACCEPTED=1")

    assert armed < current_link < smoke < accepted
    assert 'return "${original_status}"' in source
    assert 'exit "${status}"' in source
    assert "rollback encountered additional failures" in source


def test_generated_token_is_written_only_to_the_restricted_file() -> None:
    source = INSTALLER.read_text(encoding="utf-8")

    assert "os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600" in source
    assert "print(token)" not in source
    assert "print(next(grant.token" not in source
    assert "JACOBIAN_MCP_AUTH_TOKENS_FILE" in source
    assert "generated bearer token: ${" not in source
    assert "retrieve it explicitly with privileged access" in source


def test_rollback_restores_prior_service_activity_and_enablement(
    tmp_path: Path,
) -> None:
    state = tmp_path / "systemd-state"
    snapshots = tmp_path / "snapshots"
    state.mkdir()
    snapshots.mkdir()
    fake_systemctl = tmp_path / "systemctl"
    fake_systemctl.write_text(
        """#!/usr/bin/env bash
set -eu
action="$1"
case "$action" in
  is-enabled) test -f "$FAKE_SYSTEMD_STATE/$3.enabled" ;;
  is-active) test -f "$FAKE_SYSTEMD_STATE/$3.active" ;;
  enable) : >"$FAKE_SYSTEMD_STATE/$2.enabled" ;;
  disable) rm -f -- "$FAKE_SYSTEMD_STATE/$2.enabled" ;;
  restart) : >"$FAKE_SYSTEMD_STATE/$2.active" ;;
  stop) rm -f -- "$FAKE_SYSTEMD_STATE/$2.active" ;;
  *) exit 2 ;;
esac
""",
        encoding="utf-8",
    )
    fake_systemctl.chmod(0o755)
    (state / "jacobian-mcp.service.enabled").touch()
    (state / "jacobian-mcp.service.active").touch()
    (state / "jacobian-caddy.service.enabled").touch()
    environment = os.environ | {"FAKE_SYSTEMD_STATE": str(state)}
    units = (
        "jacobian-mcp.service",
        "jacobian-caddy.service",
        "jacobian-funnel.service",
    )

    for unit in units:
        subprocess.run(
            [
                "bash",
                "-c",
                'source "$1"; snapshot_systemd_service_state "$2" "$3" "$4"',
                "service-state-test",
                str(SERVICE_STATE),
                str(fake_systemctl),
                str(snapshots),
                unit,
            ],
            check=True,
            env=environment,
        )
        (state / f"{unit}.enabled").touch()
        (state / f"{unit}.active").touch()

    for unit in units:
        subprocess.run(
            [
                "bash",
                "-c",
                'source "$1"; restore_systemd_service_state "$2" "$3" "$4"',
                "service-state-test",
                str(SERVICE_STATE),
                str(fake_systemctl),
                str(snapshots),
                unit,
            ],
            check=True,
            env=environment,
        )

    assert (state / "jacobian-mcp.service.enabled").is_file()
    assert (state / "jacobian-mcp.service.active").is_file()
    assert (state / "jacobian-caddy.service.enabled").is_file()
    assert not (state / "jacobian-caddy.service.active").exists()
    assert not (state / "jacobian-funnel.service.enabled").exists()
    assert not (state / "jacobian-funnel.service.active").exists()
