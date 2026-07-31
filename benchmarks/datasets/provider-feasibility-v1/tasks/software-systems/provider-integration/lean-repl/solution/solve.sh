#!/bin/sh
set -eu
mkdir -p /app/evidence
python /app/spike.py \
  --checkout /opt/provider/repl \
  --repl /opt/provider/repl/.lake/build/bin/repl \
  --output /app/evidence/provider-report.json
python /solution/solve.py
