#!/bin/sh
set -eu
mkdir -p /app/evidence
python /app/spike.py \
  --executable /opt/provider/cgal-spike \
  --source-archive /opt/provider/cgal.tar.xz \
  --output /app/evidence/provider-report.json
python /solution/solve.py
