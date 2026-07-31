#!/bin/sh
set -eu
mkdir -p /app/evidence
python /app/spike.py \
  --geng /opt/provider/nauty2_9_3/geng \
  --labelg /opt/provider/nauty2_9_3/labelg \
  --source-archive /opt/provider/nauty.tar.gz \
  --output /app/evidence/provider-report.json
python /solution/solve.py
