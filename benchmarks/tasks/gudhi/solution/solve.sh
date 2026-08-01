#!/bin/sh
set -eu
mkdir -p /app/evidence
python /app/spike.py \
  --python-executable /usr/local/bin/python \
  --wheel /opt/provider/gudhi.whl \
  --source-archive /opt/provider/gudhi-source.tar.gz \
  --pin /app/pin.json \
  --output /app/evidence/provider-report.json
python /solution/solve.py
