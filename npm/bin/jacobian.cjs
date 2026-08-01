#!/usr/bin/env node

"use strict";

const { stderr } = require("node:process");

/**
 * Jacobian CLI entry point.
 *
 * Subcommands handled in Node:
 *   jacobian setup    — MCP client configuration wizard
 *   jacobian upgrade  — Refresh the launcher-managed Python package
 *   jacobian doctor   — MCP handshake and tool catalog verification
 *   jacobian remove   — Remove Jacobian MCP from client configs
 *   jacobian mcp      — Run the MCP server over stdio
 *
 * Everything else is forwarded to the Python `jacobian` CLI.
 */

const HELP = `Jacobian — composable mathematical capabilities for AI agents

Usage:
  jacobian setup [--client <id>...] [--all] [--yes] [--dry-run] [--json]
                 [--source <checkout> --state-dir <path> --profile <name>]
    Configure MCP clients to use Jacobian.
  jacobian upgrade
    Refresh the launcher-managed Python package.
  jacobian doctor [--json]
    Verify the MCP handshake and tool catalog.
  jacobian remove [--client <id>...] [--all] [--yes] [--json]
    Remove Jacobian from MCP client configs.
  jacobian mcp
    Run the Jacobian MCP server over stdio.
  jacobian <command> [args...]
    Forward to the Python Jacobian CLI.

Clients:
  claude, cursor, opencode, codex, gemini

Environment:
  JACOBIAN_STATE_DIR    State directory (default: ./.jacobian)
  JACOBIAN_PACKAGE      Python package spec (default: jacobian)
`;

function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  if (!command || command === "--help" || command === "-h") {
    stderr.write(HELP);
    return;
  }

  if (command === "--version" || command === "-v") {
    const pkg = require("../package.json");
    console.log(`jacobian ${pkg.version}`);
    return;
  }

  if (command === "setup") {
    const setup = require("./setup.cjs");
    const rest = args.slice(1);
    const options = { operation: "setup" };
    for (let i = 0; i < rest.length; i++) {
      const arg = rest[i];
      if (arg === "--all") {
        options.all = true;
      } else if (arg === "--yes" || arg === "-y") {
        options.yes = true;
      } else if (arg === "--dry-run") {
        options.dryRun = true;
      } else if (arg === "--json") {
        options.json = true;
      } else if (arg === "--source") {
        options.source = rest[++i];
      } else if (arg.startsWith("--source=")) {
        options.source = arg.slice(9);
      } else if (arg === "--state-dir") {
        options.stateDir = rest[++i];
      } else if (arg.startsWith("--state-dir=")) {
        options.stateDir = arg.slice(12);
      } else if (arg === "--uv-bin") {
        options.uvBin = rest[++i];
      } else if (arg.startsWith("--uv-bin=")) {
        options.uvBin = arg.slice(9);
      } else if (arg === "--profile") {
        options.profile = rest[++i];
      } else if (arg.startsWith("--profile=")) {
        options.profile = arg.slice(10);
      } else if (arg === "--provider-path") {
        options.providerPath = rest[++i];
      } else if (arg.startsWith("--provider-path=")) {
        options.providerPath = arg.slice(16);
      } else if (arg === "--project-environment") {
        options.projectEnvironment = rest[++i];
      } else if (arg.startsWith("--project-environment=")) {
        options.projectEnvironment = arg.slice(22);
      } else if (arg === "--elan-home") {
        options.elanHome = rest[++i];
      } else if (arg.startsWith("--elan-home=")) {
        options.elanHome = arg.slice(12);
      } else if (arg === "--client" || arg === "-c") {
        i++;
        if (rest[i]) {
          options.clients = options.clients || [];
          options.clients.push(...rest[i].split(",").map((s) => s.trim()));
        }
      } else if (arg.startsWith("--client=")) {
        options.clients = options.clients || [];
        options.clients.push(...arg.slice(9).split(",").map((s) => s.trim()));
      }
    }
    setup.run(options).catch((error) => {
      stderr.write(
        `Jacobian setup did not finish: ${error.message}\n` +
          "No additional setup changes will be made. Correct the reported problem, " +
          "then retry `npx jacobian setup`.\n",
      );
      process.exitCode = 1;
    });
    return;
  }

  if (command === "upgrade") {
    const { PACKAGE_SPEC, upgrade } = require("./launcher.cjs");
    try {
      upgrade();
      console.log(`Jacobian Python package upgraded to ${PACKAGE_SPEC}.`);
    } catch (error) {
      stderr.write(
        `Jacobian upgrade did not finish: ${error.message}\n` +
          "Check the local Python runtime and package index, then retry `npx jacobian upgrade`.\n",
      );
      process.exitCode = 1;
    }
    return;
  }

  if (command === "remove") {
    const setup = require("./setup.cjs");
    const rest = args.slice(1);
    const options = { operation: "remove" };
    for (let i = 0; i < rest.length; i++) {
      const arg = rest[i];
      if (arg === "--all") {
        options.all = true;
      } else if (arg === "--yes" || arg === "-y") {
        options.yes = true;
      } else if (arg === "--json") {
        options.json = true;
      } else if (arg === "--client" || arg === "-c") {
        i++;
        if (rest[i]) {
          options.clients = options.clients || [];
          options.clients.push(...rest[i].split(",").map((s) => s.trim()));
        }
      } else if (arg.startsWith("--client=")) {
        options.clients = options.clients || [];
        options.clients.push(...arg.slice(9).split(",").map((s) => s.trim()));
      }
    }
    setup.run(options).catch((error) => {
      stderr.write(
        `Jacobian removal did not finish: ${error.message}\n` +
          "Inspect the named client configuration, then retry `npx jacobian remove`.\n",
      );
      process.exitCode = 1;
    });
    return;
  }

  if (command === "doctor") {
    const doctor = require("./doctor.cjs");
    const rest = args.slice(1);
    const json = rest.includes("--json") || rest.includes("-j");
    doctor.run({ json }).catch((error) => {
      stderr.write(
        `Jacobian diagnostics did not finish: ${error.message}\n` +
          "Run `npx jacobian setup`, then retry `npx jacobian doctor`.\n",
      );
      process.exitCode = 1;
    });
    return;
  }

  if (command === "mcp") {
    const { launch } = require("./launcher.cjs");
    try {
      launch("jacobian.adapters.mcp.server", args.slice(1));
    } catch (error) {
      stderr.write(`Jacobian MCP could not start: ${error.message}\n`);
      process.exitCode = 1;
    }
    return;
  }

  // Forward everything else to the Python CLI.
  const { launch } = require("./launcher.cjs");
  try {
    launch("jacobian.cli", args);
  } catch (error) {
    stderr.write(`Jacobian could not start: ${error.message}\n`);
    process.exitCode = 1;
  }
}

main();
