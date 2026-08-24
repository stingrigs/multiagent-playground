#!/usr/bin/env bash
# Convenience launcher — not part of the assignment, not committed.
# Starts all 5 servers in the background (skipping any already up), waits
# for each to be reachable, then runs the REPL. Safe to run twice.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

mkdir -p /tmp/research-team-logs
PIDFILE=/tmp/research-team-logs/pids
touch "$PIDFILE"

reachable() {
    curl -s -o /dev/null --max-time 1 "$1"
}

start_if_down() {
    local name="$1" check_url="$2"; shift 2
    if reachable "$check_url"; then
        echo "  already up  $name"
        return
    fi
    "$@" > "/tmp/research-team-logs/${name}.log" 2>&1 &
    echo $! >> "$PIDFILE"
    echo "  started     $name (pid $!)"
}

wait_for() {
    local url="$1" label="$2"
    until reachable "$url"; do sleep 1; done
    echo "  ready       $label"
}

echo "Starting MCP servers..."
start_if_down search_mcp http://127.0.0.1:8901/mcp .venv/bin/python mcp_servers/search_mcp.py
start_if_down report_mcp http://127.0.0.1:8902/mcp .venv/bin/python mcp_servers/report_mcp.py
wait_for http://127.0.0.1:8901/mcp SearchMCP
wait_for http://127.0.0.1:8902/mcp ReportMCP

echo "Starting A2A servers..."
# one process serves all 3 ports — check the first as a proxy for "already running"
start_if_down a2a_servers http://127.0.0.1:8903/.well-known/agent-card.json \
    .venv/bin/python a2a_servers.py
wait_for http://127.0.0.1:8903/.well-known/agent-card.json Planner
wait_for http://127.0.0.1:8904/.well-known/agent-card.json Researcher
wait_for http://127.0.0.1:8905/.well-known/agent-card.json Critic

echo ""
echo "All 5 servers up. Logs in /tmp/research-team-logs/. Starting REPL..."
echo ""
.venv/bin/python main.py
