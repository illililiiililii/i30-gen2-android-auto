"""Smoke-test the i30-rea Codex entry with two offline metadata calls."""

import json
import subprocess
import argparse
from pathlib import Path

from inspect_firmware import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=ROOT / "firmware/original/install.exe")
    args = parser.parse_args()
    config = subprocess.run(
        ["codex", "mcp", "get", "i30-rea", "--json"],
        capture_output=True, text=True, check=True,
    )
    from os import environ
    transport = json.loads(config.stdout)["transport"]
    environment = dict(environ, **transport["env"])
    target = args.target.resolve()
    with subprocess.Popen(
        [transport["command"], *transport["args"]], env=environment,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, encoding="utf-8",
    ) as process:
        def request(method, params, request_id=None):
            message = {"jsonrpc": "2.0", "method": method, "params": params}
            if request_id is not None:
                message["id"] = request_id
            process.stdin.write(json.dumps(message) + "\n")
            process.stdin.flush()
            if request_id is None:
                return None
            for line in process.stdout:
                response = json.loads(line)
                if response.get("id") != request_id:
                    continue
                if "error" in response or response["result"].get("isError"):
                    raise RuntimeError(f"MCP operation failed: {response}")
                return response["result"]
            raise RuntimeError(f"MCP server stopped during {method}")

        try:
            info = request("initialize", {
                "protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "i30-phase0", "version": "1"},
            }, 1)
            request("notifications/initialized", {})
            names = {tool["name"] for tool in request("tools/list", {}, 2)["tools"]}
            calls = {}
            for request_id, tool in enumerate(("inspect_pe_imports", "inspect_pe_certificates"), 3):
                if tool not in names:
                    raise RuntimeError(f"Expected tool absent: {tool}")
                result = request("tools/call", {"name": tool, "arguments": {"path": str(target)}}, request_id)
                calls[tool] = result.get("structuredContent") or result["content"]
        finally:
            process.terminate()

    display_path = target.relative_to(ROOT) if target.is_relative_to(ROOT) else target
    evidence = {"server": info["serverInfo"], "tool_count": len(names),
                "target": display_path.as_posix(), "results": calls}
    name = "rea-smoke.json" if target.name == "install.exe" else f"rea-smoke-{target.name}.json"
    (ROOT / "research/evidence" / name).write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"{info['serverInfo']}: {len(names)} listed tools, {len(calls)} successful calls")


if __name__ == "__main__":
    main()
