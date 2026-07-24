#!/usr/bin/env node

"use strict";

const { stderr } = require("node:process");

/**
 * Jacobian CLI entry point.
 *
 * Subcommands handled in Node:
 *   jacobian setup    — MCP client configuration wizard
 *   jacobian doctor   — MCP handshake and tool catalog verification
 *   jacobian remove   — Remove Jacobian MCP from client configs
 *   jacobian mcp      — Run the MCP server over stdio
 *
 * Everything else is forwarded to the Python `jacobian` CLI.
 */

const HELP = `Jacobian — verifier-centric MCP toolbench for bounded executable mathematics

Usage:
  jacobian setup [--client <id>...] [--all] [--yes] [--dry-run] [--json]
    Configure MCP clients to use Jacobian.
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
  JACOBIAN_PACKAGE      Python package spec (default: jacobian-research-kernel)
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
      stderr.write(`Setup failed: ${error.message}\n`);
      process.exitCode = 1;
    });
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
      stderr.write(`Remove failed: ${error.message}\n`);
      process.exitCode = 1;
    });
    return;
  }

  if (command === "doctor") {
    const doctor = require("./doctor.cjs");
    const rest = args.slice(1);
    const json = rest.includes("--json") || rest.includes("-j");
    doctor.run({ json }).catch((error) => {
      stderr.write(`Doctor failed: ${error.message}\n`);
      process.exitCode = 1;
    });
    return;
  }

  if (command === "mcp") {
    const { launch } = require("./launcher.cjs");
    launch("jacobian.adapters.mcp.server", args.slice(1));
    return;
  }

  // Forward everything else to the Python CLI.
  const { launch } = require("./launcher.cjs");
  launch("jacobian.cli", args);
}

main();
