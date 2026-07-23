"""Installation and immutable resolution of untrusted domain plugins."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from jacobian.contracts.plugins import (
    CapabilityDescriptor,
    CapabilityName,
    PluginManifest,
)
from jacobian.implementation import (
    ImplementationError,
    module_source_digest,
)
from jacobian.store import ArtifactStore, StoreError


class PluginRegistryError(RuntimeError):
    """A plugin manifest or implementation binding is invalid."""


@dataclass(frozen=True, slots=True)
class ResolvedCapability:
    """A plugin capability bound to the source digest measured at resolution."""

    plugin_id: str
    name: CapabilityName
    descriptor: CapabilityDescriptor
    implementation_digest: str


class PluginRegistry:
    """Operator-installed plugin metadata without checker authorization."""

    def __init__(self, store: ArtifactStore) -> None:
        self.store = store
        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.store.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS installed_plugins (
                    plugin_id TEXT PRIMARY KEY,
                    domain_id TEXT NOT NULL,
                    domain_version TEXT NOT NULL,
                    installed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def register_implementation(self, entrypoint: str) -> str:
        """Record an operator-installed entrypoint and its current source digest."""

        try:
            digest = module_source_digest(entrypoint)
        except ImplementationError as exc:
            raise PluginRegistryError(str(exc)) from exc
        return self.store.register_descriptor(
            kind="implementation",
            name=entrypoint,
            version="1",
            definition={
                "entrypoint": entrypoint,
                "module_digest": digest,
            },
        )

    def install(self, plugin_id: str) -> PluginManifest:
        """Install a manifest after resolving every immutable dependency."""

        try:
            artifact = self.store.get(plugin_id)
            manifest = PluginManifest.model_validate(artifact.payload)
            self.store.get_descriptor(
                manifest.semantics_uri,
                expected_kind="semantics",
            )
            self.store.get_descriptor(
                manifest.claim_schema_uri,
                expected_kind="schema",
            )
            self.store.get_descriptor(
                manifest.candidate_schema_uri,
                expected_kind="schema",
            )
            for schema_uri in (
                *manifest.witness_schema_uris,
                *manifest.certificate_schema_uris,
            ):
                self.store.get_descriptor(schema_uri, expected_kind="schema")
            for descriptor in manifest.capabilities.values():
                implementation = self.store.get_descriptor(
                    descriptor.implementation_uri,
                    expected_kind="implementation",
                )
                definition = implementation.get("definition")
                if not isinstance(definition, dict):
                    raise PluginRegistryError(
                        "implementation descriptor has no object definition"
                    )
                if definition.get("entrypoint") != descriptor.entrypoint:
                    raise PluginRegistryError(
                        "capability entrypoint differs from implementation binding"
                    )
                expected_digest = definition.get("module_digest")
                if expected_digest != module_source_digest(descriptor.entrypoint):
                    raise PluginRegistryError(
                        "plugin implementation bytes differ from its binding"
                    )
        except (StoreError, ValueError, ImplementationError) as exc:
            raise PluginRegistryError(str(exc)) from exc

        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO installed_plugins (
                    plugin_id, domain_id, domain_version
                ) VALUES (?, ?, ?)
                """,
                (
                    plugin_id,
                    manifest.domain_id,
                    manifest.domain_version,
                ),
            )
            row = connection.execute(
                """
                SELECT domain_id, domain_version
                FROM installed_plugins
                WHERE plugin_id = ?
                """,
                (plugin_id,),
            ).fetchone()
        if row is None or (
            row["domain_id"],
            row["domain_version"],
        ) != (manifest.domain_id, manifest.domain_version):
            raise PluginRegistryError("installed plugin metadata mismatch")
        return manifest

    def get(self, plugin_id: str) -> PluginManifest:
        """Return an installed manifest without resolving executable code."""

        with self._connect() as connection:
            installed = connection.execute(
                "SELECT 1 FROM installed_plugins WHERE plugin_id = ?",
                (plugin_id,),
            ).fetchone()
        if installed is None:
            raise PluginRegistryError(f"plugin is not installed: {plugin_id}")
        try:
            return PluginManifest.model_validate(self.store.get(plugin_id).payload)
        except (StoreError, ValueError) as exc:
            raise PluginRegistryError(str(exc)) from exc

    def resolve(
        self,
        plugin_id: str,
        capability: CapabilityName,
    ) -> ResolvedCapability:
        """Resolve a capability only if its source still matches installation."""

        manifest = self.get(plugin_id)
        descriptor = manifest.capabilities.get(capability)
        if descriptor is None:
            raise PluginRegistryError(f"plugin does not implement {capability.value}")
        try:
            implementation = self.store.get_descriptor(
                descriptor.implementation_uri,
                expected_kind="implementation",
            )
            definition = implementation.get("definition")
            if not isinstance(definition, dict):
                raise PluginRegistryError(
                    "implementation descriptor has no object definition"
                )
            expected_digest = definition.get("module_digest")
            actual_digest = module_source_digest(descriptor.entrypoint)
            if definition.get("entrypoint") != descriptor.entrypoint:
                raise PluginRegistryError(
                    "capability entrypoint differs from implementation binding"
                )
            if expected_digest != actual_digest:
                raise PluginRegistryError(
                    "plugin implementation bytes changed after installation"
                )
        except (StoreError, ImplementationError) as exc:
            raise PluginRegistryError(str(exc)) from exc
        return ResolvedCapability(
            plugin_id=plugin_id,
            name=capability,
            descriptor=descriptor,
            implementation_digest=actual_digest,
        )
