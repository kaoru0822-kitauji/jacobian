"use strict";

const { spawn } = require("node:child_process");
const { join } = require("node:path");
const { stderr, stdout } = require("node:process");

/**
 * Jacobian MCP doctor.
 *
 * Launches the Jacobian MCP server as a subprocess, performs the MCP
 * initialize handshake, lists tools, and verifies that the expected tool
 * catalog is present.  Reports structured status to stderr (human-readable)
 * or stdout (JSON with --json).
 */

const PROTOCOL_VERSION = "2025-11-25";
const HANDSHAKE_TIMEOUT_MS = 60_000;
const RESPONSE_TIMEOUT_MS = 10_000;

const EXPECTED_TOOLS = [
  "artifact.put",
  "claim.validate",
  "evaluate.batch",
  "witness.find",
  "witness.verify",
  "shrink.run",
  "certificate.verify",
  "structure.canonicalize",
  "search.enumerate",
  "search.run",
  "experiment.cancel",
  "experiment.pause",
  "experiment.resume",
  "transform.apply",
  "transform.verify",
  "polytope.separate",
  "conjecture.repair",
  "conjecture.generate",
  "parameter.generalize",
  "parameter.region.promote",
];

/**
 * @typedef {object} DoctorReport
 * @property {string} status  "ok" | "error"
 * @property {string} serverName
 * @property {string} serverVersion
 * @property {boolean} instructionsLoaded
 * @property {string[]} tools
 * @property {object} integration
 * @property {string} integration.launcherStatus
 * @property {string} integration.handshakeStatus
 * @property {string} integration.catalogStatus
 * @property {string} integration.repairCommand
 * @property {object} firstCall
 * @property {string} firstCall.status
 */

/**
 * Send a JSON-RPC message to the server's stdin.
 *
 * @param {import("node:child_process").ChildProcessWithoutNullStreams} child
 * @param {object} message
 */
function sendMessage(child, message) {
  const data = JSON.stringify(message) + "\n";
  child.stdin.write(data);
}

/**
 * Wait for a JSON-RPC response with a specific id.
 *
 * @param {import("node:child_process").ChildProcessWithoutNullStreams} child
 * @param {number} id
 * @param {number} timeoutMs
 * @returns {Promise<object>}
 */
function waitForResponse(child, id, timeoutMs) {
  return new Promise((resolve, reject) => {
    let buffer = "";
    const timer = setTimeout(() => {
      reject(new Error(`timed out after ${timeoutMs}ms waiting for response id=${id}`));
    }, timeoutMs);

    child.stdout.on("data", (chunk) => {
      buffer += chunk.toString();
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const message = JSON.parse(line);
          if (message.id === id) {
            clearTimeout(timer);
            resolve(message);
            return;
          }
        } catch {
          // Ignore non-JSON lines (server stderr noise).
        }
      }
    });

    child.once("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });

    child.once("close", (code) => {
      clearTimeout(timer);
      reject(new Error(`server exited with code ${code} before responding`));
    });
  });
}

/**
 * Run the doctor diagnostic.
 *
 * @param {object} [options]
 * @param {boolean} [options.json]
 * @returns {Promise<DoctorReport>}
 */
async function run(options = {}) {
  const json = options.json ?? false;
  const launcher = require("./launcher.cjs");

  if (!json) {
    stderr.write("◇ Jacobian is checking the MCP handshake and tool catalog...\n");
  }

  // Resolve the Python executable and spawn the MCP server.
  let python;
  try {
    python = launcher.resolvePython();
  } catch (error) {
    const report = {
      status: "error",
      serverName: "",
      serverVersion: "",
      instructionsLoaded: false,
      tools: [],
      integration: {
        launcherStatus: "failed",
        handshakeStatus: "not_attempted",
        catalogStatus: "not_attempted",
        repairCommand: "npx jacobian setup",
      },
      firstCall: { status: "not_attempted" },
      error: error.message,
    };
    if (json) {
      stdout.write(JSON.stringify(report, null, 2) + "\n");
    } else {
      stderr.write(`  ✗ Launcher failed: ${error.message}\n`);
      stderr.write(`  Run \`npx jacobian setup\` to configure MCP clients.\n`);
    }
    process.exitCode = 1;
    return report;
  }

  const stateDir = process.env.JACOBIAN_STATE_DIR || join(process.cwd(), ".jacobian");
  const child = spawn(python, ["-m", "jacobian.adapters.mcp.server"], {
    stdio: ["pipe", "pipe", "inherit"],
    env: { ...process.env, JACOBIAN_STATE_DIR: stateDir },
    windowsHide: true,
  });

  const version = require("../package.json").version;

  try {
    // 1. Initialize handshake.
    sendMessage(child, {
      jsonrpc: "2.0",
      id: 1,
      method: "initialize",
      params: {
        protocolVersion: PROTOCOL_VERSION,
        capabilities: {},
        clientInfo: {
          name: "jacobian-doctor",
          version,
        },
      },
    });

    const initResponse = await waitForResponse(child, 1, HANDSHAKE_TIMEOUT_MS);
    if (initResponse.error) {
      throw new Error(`initialize failed: ${JSON.stringify(initResponse.error)}`);
    }
    const result = initResponse.result;
    const serverName = result?.serverInfo?.name ?? "";
    const serverVersion = result?.serverInfo?.version ?? "";
    const instructionsLoaded = typeof result?.instructions === "string";

    if (serverName !== "jacobian") {
      throw new Error(`MCP identified itself as "${serverName}", expected "jacobian"`);
    }

    // 2. Send initialized notification.
    sendMessage(child, {
      jsonrpc: "2.0",
      method: "notifications/initialized",
      params: {},
    });

    // 3. List tools.
    sendMessage(child, {
      jsonrpc: "2.0",
      id: 2,
      method: "tools/list",
      params: {},
    });

    const toolsResponse = await waitForResponse(child, 2, RESPONSE_TIMEOUT_MS);
    if (toolsResponse.error) {
      throw new Error(`tools/list failed: ${JSON.stringify(toolsResponse.error)}`);
    }
    const tools = (toolsResponse.result?.tools ?? []).map((t) => t.name);
    const missingTools = EXPECTED_TOOLS.filter((t) => !tools.includes(t));
    const catalogStatus = missingTools.length === 0 ? "complete" : "partial";

    const report = {
      status: missingTools.length === 0 ? "ok" : "error",
      serverName,
      serverVersion,
      instructionsLoaded,
      tools,
      integration: {
        launcherStatus: "ok",
        handshakeStatus: "ok",
        catalogStatus,
        repairCommand: "npx jacobian setup",
      },
      firstCall: { status: "not_attempted" },
      missingTools,
    };

    child.kill("SIGTERM");

    if (json) {
      stdout.write(JSON.stringify(report, null, 2) + "\n");
    } else {
      stderr.write(`\n  ✓ Launcher: ok\n`);
      stderr.write(`  ✓ Handshake: ok (server: ${serverName} ${serverVersion})\n`);
      stderr.write(`  ${catalogStatus === "complete" ? "✓" : "✗"} Tool catalog: ${catalogStatus} (${tools.length} tools)\n`);
      if (missingTools.length > 0) {
        stderr.write(`    Missing: ${missingTools.join(", ")}\n`);
      }
      stderr.write(`\n  ${report.status === "ok" ? "✓ Jacobian MCP is ready." : "✗ Jacobian MCP has issues."}\n`);
      stderr.write(`  Run \`npx jacobian setup\` to configure or repair MCP clients.\n\n`);
    }

    if (report.status !== "ok") {
      process.exitCode = 1;
    }
    return report;
  } catch (error) {
    child.kill("SIGTERM");
    const report = {
      status: "error",
      serverName: "",
      serverVersion: "",
      instructionsLoaded: false,
      tools: [],
      integration: {
        launcherStatus: "ok",
        handshakeStatus: "failed",
        catalogStatus: "not_attempted",
        repairCommand: "npx jacobian setup",
      },
      firstCall: { status: "not_attempted" },
      error: error.message,
    };
    if (json) {
      stdout.write(JSON.stringify(report, null, 2) + "\n");
    } else {
      stderr.write(`\n  ✓ Launcher: ok\n`);
      stderr.write(`  ✗ Handshake failed: ${error.message}\n`);
      stderr.write(`  Run \`npx jacobian setup\` to configure or repair MCP clients.\n\n`);
    }
    process.exitCode = 1;
    return report;
  }
}

module.exports = { run, EXPECTED_TOOLS };
