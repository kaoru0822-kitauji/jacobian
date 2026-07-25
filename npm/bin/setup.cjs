"use strict";

const {
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
  rmSync,
} = require("node:fs");
const { homedir } = require("node:os");
const { dirname, join } = require("node:path");
const readline = require("node:readline/promises");
const { stdin, stdout, stderr } = require("node:process");

/**
 * Jacobian MCP setup wizard.
 *
 * Detects installed MCP clients (Claude Code, Cursor, Codex, Gemini CLI,
 * OpenCode), shows the user which were found, and writes MCP server
 * configurations that launch `npx jacobian mcp` as a stdio server.
 *
 * The wizard never auto-selects detected clients.  Detection is context,
 * not consent.
 */

const SERVER_NAME = "jacobian";

/**
 * @typedef {"claude" | "cursor" | "opencode" | "codex" | "gemini"} ClientId
 */

/**
 * @typedef {object} ClientDef
 * @property {ClientId} id
 * @property {string} displayName
 * @property {"json" | "toml"} format
 * @property {string} configPath
 * @property {string} jsonSection  Section key for JSON configs.
 * @property {"command_args" | "opencode"} jsonShape
 */

/**
 * @param {string} home
 * @returns {ClientDef[]}
 */
function clientDefinitions(home) {
  return [
    {
      id: "claude",
      displayName: "Claude Code",
      format: "json",
      configPath: join(home, ".claude.json"),
      jsonSection: "mcpServers",
      jsonShape: "command_args",
    },
    {
      id: "cursor",
      displayName: "Cursor",
      format: "json",
      configPath: join(home, ".cursor", "mcp.json"),
      jsonSection: "mcpServers",
      jsonShape: "command_args",
    },
    {
      id: "opencode",
      displayName: "OpenCode",
      format: "json",
      configPath: join(home, ".config", "opencode", "opencode.json"),
      jsonSection: "mcp",
      jsonShape: "opencode",
    },
    {
      id: "codex",
      displayName: "Codex",
      format: "toml",
      configPath: join(home, ".codex", "config.toml"),
      jsonSection: "",
      jsonShape: "command_args",
    },
    {
      id: "gemini",
      displayName: "Gemini CLI",
      format: "json",
      configPath: join(home, ".gemini", "settings.json"),
      jsonSection: "mcpServers",
      jsonShape: "command_args",
    },
  ];
}

/**
 * @param {string} home
 * @param {ClientId} id
 * @returns {boolean}
 */
function isClientDetected(home, id) {
  switch (id) {
    case "claude":
      return existsSync(join(home, ".claude")) || existsSync(join(home, ".claude.json"));
    case "cursor":
      return existsSync(join(home, ".cursor"));
    case "opencode":
      return existsSync(join(home, ".config", "opencode"));
    case "codex":
      return existsSync(join(home, ".codex"));
    case "gemini":
      return existsSync(join(home, ".gemini"));
    default:
      return false;
  }
}

/**
 * Build the MCP launcher command + args that will be written to client configs.
 *
 * When running under npx, pins the exact version.  When running from a
 * persistent install, uses the installed binary directly.
 *
 * @returns {{ command: string, args: string[], version: string, package: string | null }}
 */
function buildLauncher() {
  const version = require("../package.json").version;

  if (process.env.npm_lifecycle_event === "npx") {
    const node = process.env.npm_node_execpath;
    const npm = process.env.npm_execpath;
    if (node && npm) {
      const pkg = `jacobian@${version}`;
      return {
        command: node,
        args: [npm, "exec", "--yes", `--package=${pkg}`, "--", "jacobian", "mcp"],
        version,
        package: pkg,
      };
    }
  }

  // Persistent install: use the bin directly with the mcp subcommand.
  const binPath = process.argv[1] || "jacobian";
  return {
    command: process.execPath,
    args: [binPath, "mcp"],
    version,
    package: null,
  };
}

/**
 * Build the MCP server entry value for a JSON config.
 *
 * @param {ClientDef} def
 * @param {{ command: string, args: string[] }} launcher
 * @returns {object}
 */
function jsonEntry(def, launcher) {
  if (def.jsonShape === "opencode") {
    return {
      type: "local",
      command: [launcher.command, ...launcher.args].join(" "),
      cwd: ".",
      enabled: true,
    };
  }
  return {
    command: launcher.command,
    args: launcher.args,
  };
}

/**
 * Read a file if it exists, returning null otherwise.
 *
 * @param {string} path
 * @returns {string | null}
 */
function readOptional(path) {
  try {
    return readFileSync(path, "utf8");
  } catch (error) {
    if (error.code === "ENOENT") return null;
    throw error;
  }
}

/**
 * Write a file only if its content would change.
 *
 * @param {string} path
 * @param {string} content
 */
function writeIfChanged(path, content) {
  const existing = readOptional(path);
  if (existing === content) return;
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, content, { encoding: "utf8" });
}

/**
 * Resolve a JSON config edit for setup or removal.
 *
 * @param {"setup" | "remove"} operation
 * @param {ClientDef} def
 * @param {{ command: string, args: string[] }} launcher
 * @returns {{ action: string, original: string | null, updated: string | null }}
 */
function resolveJsonEdit(operation, def, launcher) {
  const original = readOptional(def.configPath);
  const source = original ?? "{}\n";
  let root;
  try {
    root = JSON.parse(source);
  } catch (error) {
    throw new Error(
      `Invalid JSON in ${def.configPath}: ${error.message}. No changes were written. ` +
        "Repair this file, then retry.",
    );
  }
  if (typeof root !== "object" || root === null || Array.isArray(root)) {
    throw new Error(
      `Top-level value in ${def.configPath} must be an object. No changes were ` +
        "written. Repair this file, then retry.",
    );
  }
  const section = root[def.jsonSection] ?? {};
  if (typeof section !== "object" || section === null || Array.isArray(section)) {
    throw new Error(
      `${def.jsonSection} in ${def.configPath} must be an object. No changes were ` +
        "written. Repair this file, then retry.",
    );
  }

  if (operation === "setup") {
    const expected = jsonEntry(def, launcher);
    if (JSON.stringify(section[SERVER_NAME]) === JSON.stringify(expected)) {
      return { action: "already_current", original, updated: null };
    }
    section[SERVER_NAME] = expected;
    root[def.jsonSection] = section;
    const updated = JSON.stringify(root, null, 2) + "\n";
    return {
      action: original === null ? "create" : "update",
      original,
      updated,
    };
  }

  // Remove
  if (!(SERVER_NAME in section)) {
    return { action: "not_configured", original, updated: null };
  }
  delete section[SERVER_NAME];
  if (Object.keys(section).length === 0) {
    delete root[def.jsonSection];
  }
  const updated = JSON.stringify(root, null, 2) + "\n";
  return { action: "remove", original, updated };
}

/**
 * Resolve a TOML config edit for setup or removal (Codex).
 *
 * Uses a minimal TOML editor that preserves the structure we need.
 *
 * @param {"setup" | "remove"} operation
 * @param {ClientDef} def
 * @param {{ command: string, args: string[] }} launcher
 * @returns {{ action: string, original: string | null, updated: string | null }}
 */
function resolveTomlEdit(operation, def, launcher) {
  const original = readOptional(def.configPath);
  const source = original ?? "";
  const lines = source.split("\n");

  // Find or create the [mcp_servers] section.
  let sectionStart = -1;
  let sectionEnd = lines.length;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].trim() === "[mcp_servers]") {
      sectionStart = i;
      // Find where this section ends (next top-level table or EOF).
      for (let j = i + 1; j < lines.length; j++) {
        if (lines[j].startsWith("[") && !lines[j].startsWith("[[")) {
          sectionEnd = j;
          break;
        }
      }
      break;
    }
  }

  if (operation === "remove") {
    if (sectionStart === -1) {
      return { action: "not_configured", original, updated: null };
    }
    // Remove the jacobian entry lines.
    const before = lines.slice(0, sectionStart);
    const sectionLines = lines.slice(sectionStart, sectionEnd);
    const after = lines.slice(sectionEnd);

    const filtered = sectionLines.filter(
      (line) => !line.trim().startsWith("jacobian"),
    );
    // If only the header remains, remove the section entirely.
    const nonHeader = filtered.filter(
      (line) => line.trim() !== "" && line.trim() !== "[mcp_servers]",
    );
    let updated;
    if (nonHeader.length === 0) {
      updated = [...before, ...after].join("\n");
    } else {
      updated = [...before, ...filtered, ...after].join("\n");
    }
    return { action: "remove", original, updated };
  }

  // Setup: build the entry.
  const entryLines = [
    `[mcp_servers]`,
    `jacobian = { command = "${launcher.command}", args = [${launcher.args.map((a) => `"${a}"`).join(", ")}], startup_timeout_sec = 30 }`,
  ];

  if (sectionStart === -1) {
    // No existing section: append.
    const updated =
      source.trim() === ""
        ? entryLines.join("\n") + "\n"
        : source.trimEnd() + "\n\n" + entryLines.join("\n") + "\n";
    return { action: original === null ? "create" : "update", original, updated };
  }

  // Check if jacobian is already there with the right config.
  const sectionLines = lines.slice(sectionStart, sectionEnd);
  const expectedEntry = `jacobian = { command = "${launcher.command}", args = [${launcher.args.map((a) => `"${a}"`).join(", ")}], startup_timeout_sec = 30 }`;
  for (const line of sectionLines) {
    if (line.trim() === expectedEntry) {
      return { action: "already_current", original, updated: null };
    }
  }

  // Replace or add the jacobian entry.
  const before = lines.slice(0, sectionStart + 1);
  const after = lines.slice(sectionStart + 1, sectionEnd);
  const rest = lines.slice(sectionEnd);

  // Remove any existing jacobian entry in the section.
  const cleanedAfter = after.filter((line) => !line.trim().startsWith("jacobian"));
  const updated = [...before, expectedEntry, ...cleanedAfter, ...rest].join("\n");
  return { action: "update", original, updated };
}

/**
 * Resolve one client edit.
 *
 * @param {"setup" | "remove"} operation
 * @param {ClientDef} def
 * @param {{ command: string, args: string[] }} launcher
 * @returns {{ client: ClientDef, action: string, detected: boolean, path: string, original: string | null, updated: string | null }}
 */
function resolveClientEdit(operation, def, launcher) {
  const result =
    def.format === "json"
      ? resolveJsonEdit(operation, def, launcher)
      : resolveTomlEdit(operation, def, launcher);
  return {
    client: def,
    action: result.action,
    detected: isClientDetected(homedir(), def.id),
    path: def.configPath,
    original: result.original,
    updated: result.updated,
  };
}

/**
 * Apply one client edit to disk.
 *
 * @param {{ path: string, original: string | null, updated: string | null, action: string }} edit
 */
function applyEdit(edit) {
  if (edit.action === "remove") {
    if (existsSync(edit.path)) {
      rmSync(edit.path, { force: true });
    }
    return;
  }
  if (edit.updated !== null) {
    writeIfChanged(edit.path, edit.updated);
  }
}

/**
 * Print the preflight plan for user confirmation.
 *
 * @param {{ operation: string, launcher: object, edits: object[] }} plan
 */
function printPlan(plan) {
  stderr.write(`\n◆ Jacobian // MCP Setup\n`);
  stderr.write(`  Launcher: ${plan.launcher.command} ${plan.launcher.args.join(" ")}\n`);
  stderr.write(`  Version:  ${plan.launcher.version}\n`);
  if (plan.launcher.package) {
    stderr.write(`  Package:  ${plan.launcher.package} (may contact npm on client restart)\n`);
  }
  stderr.write(`\n  Planned changes:\n`);
  for (const edit of plan.edits) {
    const det = edit.detected ? " [detected]" : "";
    stderr.write(`    ${edit.client.displayName}${det}: ${edit.action} → ${edit.path}\n`);
  }
  stderr.write("\n");
}

/**
 * Interactive multi-select prompt using raw terminal input.
 *
 * @param {ClientDef[]} clients
 * @param {ClientId[]} detected
 * @returns {Promise<ClientDef[]>}
 */
async function interactiveSelect(clients, detected) {
  stderr.write("\n  Select coding agents to configure (Space to toggle, Enter to confirm):\n\n");
  for (let i = 0; i < clients.length; i++) {
    const def = clients[i];
    const det = detected.includes(def.id) ? " — detected" : "";
    stderr.write(`  [ ] ${i + 1}. ${def.displayName}${det}\n`);
  }
  stderr.write("\n  Enter comma-separated numbers (e.g. 1,3) or 'all': ");

  const rl = readline.createInterface({ input: stdin, output: stderr });
  try {
    const answer = (await rl.question("")).trim();
    rl.close();
    if (answer.toLowerCase() === "all") {
      return clients;
    }
    if (!answer) return [];
    const indices = answer
      .split(/[,\s]+/)
      .map((n) => parseInt(n, 10) - 1)
      .filter((n) => n >= 0 && n < clients.length);
    return indices.map((i) => clients[i]);
  } finally {
    rl.close();
  }
}

/**
 * Interactive yes/no confirmation.
 *
 * @returns {Promise<boolean>}
 */
async function interactiveConfirm() {
  const rl = readline.createInterface({ input: stdin, output: stderr });
  try {
    const answer = (await rl.question("Apply these changes? [y/N] ")).trim().toLowerCase();
    return answer === "y" || answer === "yes";
  } finally {
    rl.close();
  }
}

/**
 * Run the setup or removal wizard.
 *
 * @param {object} options
 * @param {"setup" | "remove"} options.operation
 * @param {string[]} [options.clients] Explicit client IDs.
 * @param {boolean} [options.all] Select all clients.
 * @param {boolean} [options.yes] Skip confirmation.
 * @param {boolean} [options.dryRun] Print plan without writing.
 * @param {boolean} [options.json] Output as JSON.
 * @returns {Promise<object>} Setup report.
 */
async function run(options) {
  const operation = options.operation;
  const home = homedir();
  const defs = clientDefinitions(home);
  const launcher = buildLauncher();
  const detectedIds = defs.filter((d) => isClientDetected(home, d.id)).map((d) => d.id);

  let selected;
  if (options.all) {
    selected = defs;
  } else if (options.clients && options.clients.length > 0) {
    const wanted = new Set(options.clients);
    selected = defs.filter((d) => wanted.has(d.id));
  } else if (options.yes) {
    stderr.write("--yes requires explicit --client flags or --all; detection is not consent.\n");
    process.exitCode = 1;
    return { error: "missing client selection" };
  } else {
    selected = await interactiveSelect(defs, detectedIds);
  }

  if (selected.length === 0) {
    return { operation, cancelled: true, dryRun: false, results: [] };
  }

  const edits = selected.map((def) => resolveClientEdit(operation, def, launcher));
  const plan = { operation, launcher, edits };

  if (options.dryRun) {
    if (options.json) {
      stdout.write(JSON.stringify({ operation, cancelled: false, dryRun: true, plan, results: [] }, null, 2) + "\n");
    } else {
      printPlan(plan);
      stderr.write("  (dry-run: no changes written)\n\n");
    }
    return { operation, cancelled: false, dryRun: true, plan, results: [] };
  }

  if (!options.yes) {
    printPlan(plan);
    const confirmed = await interactiveConfirm();
    if (!confirmed) {
      return { operation, cancelled: true, dryRun: false, plan, results: [] };
    }
  } else {
    printPlan(plan);
  }

  // Apply edits.
  const results = [];
  for (const edit of edits) {
    try {
      applyEdit(edit);
      results.push({
        client: edit.client.id,
        path: edit.path,
        status: edit.action,
        error: null,
      });
    } catch (error) {
      results.push({
        client: edit.client.id,
        path: edit.path,
        status: "failed",
        error: error.message,
      });
    }
  }

  if (options.json) {
    stdout.write(JSON.stringify({ operation, cancelled: false, dryRun: false, results }, null, 2) + "\n");
  } else {
    stderr.write("\n  Setup complete.\n");
    for (const result of results) {
      const status = result.error ? `FAILED: ${result.error}` : result.status;
      stderr.write(`    ${result.client}: ${status}\n`);
    }
    stderr.write("\n  Restart or reload configured clients, then run `npx jacobian doctor` to verify.\n\n");
  }

  return { operation, cancelled: false, dryRun: false, results };
}

module.exports = {
  SERVER_NAME,
  clientDefinitions,
  isClientDetected,
  buildLauncher,
  resolveClientEdit,
  run,
};
