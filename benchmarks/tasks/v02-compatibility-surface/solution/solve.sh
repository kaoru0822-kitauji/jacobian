#!/bin/sh
set -eu
mkdir -p /app/evidence
/opt/jacobian/.venv/bin/python /app/benchmark.py --fast -o /app/evidence/pyperf.json
/opt/jacobian/.venv/bin/python /solution/solve.py
