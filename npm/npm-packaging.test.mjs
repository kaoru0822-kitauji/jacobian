import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

import {
  clientDefinitions,
  isClientDetected,
  buildLauncher,
  resolveClientEdit,
  SERVER_NAME,
} from "./bin/setup.cjs";

/**
 * Create a fake home directory with selected client markers.
 *
 * @param {string} base
 * @param {string[]} clients
 * @returns {Promise<string>}
 */
async function fakeHome(base, clients) {
  const home = await mkdtemp(join(base, "home-"));
  for (const client of clients) {
    switch (client) {
      case "claude":
        await mkdir(join(home, ".claude"), { recursive: true });
        break;
      case "cursor":
        await mkdir(join(home, ".cursor"), { recursive: true });
        break;
      case "opencode":
        await mkdir(join(home, ".config", "opencode"), { recursive: true });
        break;
      case "codex":
        await mkdir(join(home, ".codex"), { recursive: true });
        break;
      case "gemini":
        await mkdir(join(home, ".gemini"), { recursive: true });
        break;
    }
  }
  return home;
}

test("clientDefinitions returns all five supported clients", () => {
  const home = "/tmp/fake";
  const defs = clientDefinitions(home);
  assert.equal(defs.length, 5);
  assert.equal(defs[0].id, "claude");
  assert.equal(defs[1].id, "cursor");
  assert.equal(defs[2].id, "opencode");
  assert.equal(defs[3].id, "codex");
  assert.equal(defs[4].id, "gemini");
});

test("isClientDetected recognizes installed client markers", async () => {
  const base = await mkdtemp(join(tmpdir(), "jacobian-detect-"));
  try {
    const home = await fakeHome(base, ["claude", "cursor", "codex"]);
    assert.equal(isClientDetected(home, "claude"), true);
    assert.equal(isClientDetected(home, "cursor"), true);
    assert.equal(isClientDetected(home, "codex"), true);
    assert.equal(isClientDetected(home, "opencode"), false);
    assert.equal(isClientDetected(home, "gemini"), false);
  } finally {
    await rm(base, { recursive: true, force: true });
  }
});

test("buildLauncher returns a version-matching launcher with mcp subcommand", () => {
  const launcher = buildLauncher();
  const pkg = require("./package.json");
  assert.equal(launcher.version, pkg.version);
  assert.ok(launcher.command.length > 0);
  assert.ok(launcher.args.length > 0);
  // The last arg should be "mcp" (the subcommand).
  assert.equal(launcher.args[launcher.args.length - 1], "mcp");
});

test("setup writes a JSON config for Claude Code", async () => {
  const base = await mkdtemp(join(tmpdir(), "jacobian-json-"));
  try {
    const home = await fakeHome(base, ["claude"]);
    const defs = clientDefinitions(home);
    const claude = defs.find((d) => d.id === "claude");
    const launcher = { command: "/usr/bin/node", args: ["/path/to/jacobian", "mcp"], version: "0.2.0-alpha.0", package: null };

    const edit = resolveClientEdit("setup", claude, launcher);
    assert.equal(edit.action, "create");
    assert.equal(edit.original, null);
    assert.ok(edit.updated !== null);

    // Apply the edit.
    mkdirSync(join(home, ".claude"), { recursive: true });
    writeFileSync(claude.configPath, edit.updated);

    // Re-read and verify.
    const config = JSON.parse(await readFile(claude.configPath, "utf8"));
    assert.ok(config.mcpServers);
    assert.ok(config.mcpServers[SERVER_NAME]);
    assert.equal(config.mcpServers[SERVER_NAME].command, "/usr/bin/node");
    assert.deepEqual(config.mcpServers[SERVER_NAME].args, ["/path/to/jacobian", "mcp"]);

    // Re-resolving should report already_current.
    const edit2 = resolveClientEdit("setup", claude, launcher);
    assert.equal(edit2.action, "already_current");
  } finally {
    await rm(base, { recursive: true, force: true });
  }
});

test("setup writes a TOML config for Codex", async () => {
  const base = await mkdtemp(join(tmpdir(), "jacobian-toml-"));
  try {
    const home = await fakeHome(base, ["codex"]);
    const defs = clientDefinitions(home);
    const codex = defs.find((d) => d.id === "codex");
    const launcher = { command: "/usr/bin/node", args: ["/path/to/jacobian", "mcp"], version: "0.2.0-alpha.0", package: null };

    const edit = resolveClientEdit("setup", codex, launcher);
    assert.equal(edit.action, "create");
    assert.ok(edit.updated !== null);
    assert.ok(edit.updated.includes("[mcp_servers]"));
    assert.ok(edit.updated.includes("jacobian"));

    // Apply and re-read.
    mkdirSync(join(home, ".codex"), { recursive: true });
    writeFileSync(codex.configPath, edit.updated);

    // Re-resolving should report already_current.
    const edit2 = resolveClientEdit("setup", codex, launcher);
    assert.equal(edit2.action, "already_current");

    // Remove should work.
    const edit3 = resolveClientEdit("remove", codex, launcher);
    assert.equal(edit3.action, "remove");
  } finally {
    await rm(base, { recursive: true, force: true });
  }
});

test("remove on a non-configured client reports not_configured", async () => {
  const base = await mkdtemp(join(tmpdir(), "jacobian-remove-"));
  try {
    const home = await fakeHome(base, ["claude"]);
    const defs = clientDefinitions(home);
    const claude = defs.find((d) => d.id === "claude");
    const launcher = { command: "/usr/bin/node", args: ["/path/to/jacobian", "mcp"], version: "0.2.0-alpha.0", package: null };

    const edit = resolveClientEdit("remove", claude, launcher);
    assert.equal(edit.action, "not_configured");
  } finally {
    await rm(base, { recursive: true, force: true });
  }
});

test("setup updates an existing JSON config without losing other servers", async () => {
  const base = await mkdtemp(join(tmpdir(), "jacobian-update-"));
  try {
    const home = await fakeHome(base, ["claude"]);
    const defs = clientDefinitions(home);
    const claude = defs.find((d) => d.id === "claude");
    const configPath = claude.configPath;

    // Pre-populate with an existing server.
    mkdirSync(join(home, ".claude"), { recursive: true });
    const existing = {
      mcpServers: {
        "other-server": { command: "other", args: ["--foo"] },
      },
      someOtherSetting: true,
    };
    writeFileSync(configPath, JSON.stringify(existing, null, 2) + "\n");

    const launcher = { command: "/usr/bin/node", args: ["/path/to/jacobian", "mcp"], version: "0.2.0-alpha.0", package: null };
    const edit = resolveClientEdit("setup", claude, launcher);
    assert.equal(edit.action, "update");

    // Apply.
    writeFileSync(configPath, edit.updated);
    const config = JSON.parse(await readFile(configPath, "utf8"));
    assert.ok(config.mcpServers["other-server"]);
    assert.ok(config.mcpServers[SERVER_NAME]);
    assert.equal(config.someOtherSetting, true);
  } finally {
    await rm(base, { recursive: true, force: true });
  }
});
