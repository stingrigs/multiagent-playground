#!/usr/bin/env bash
# Convenience launcher — not part of the assignment, not committed.
# Kills whatever run.sh started.
PIDFILE=/tmp/research-team-logs/pids

if [ ! -f "$PIDFILE" ]; then
    echo "No pidfile — nothing started by run.sh right now."
    exit 0
fi

while read -r pid; do
    kill "$pid" 2>/dev/null && echo "  stopped pid $pid"
done < "$PIDFILE"

rm -f "$PIDFILE"
