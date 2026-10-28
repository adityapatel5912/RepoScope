#!/usr/bin/env node
/**
 * reposcope-mcp
 * Node CLI launcher delegating to the Python MCP server runtime.
 */
const { spawn } = require("child_process");

const args = process.argv.slice(2);
const pythonCmd = process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");

const child = spawn(pythonCmd, ["-m", "mcp_server.server", ...args], {
  stdio: "inherit",
  env: process.env,
});

child.on("error", (err) => {
  console.error(`[reposcope-mcp] Failed to spawn Python MCP runtime: ${err.message}`);
  process.exit(1);
});

child.on("exit", (code) => {
  process.exit(code ?? 0);
});
