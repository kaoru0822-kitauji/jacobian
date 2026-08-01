#!/bin/sh
set -eu
mkdir -p /app/evidence
python /app/spike.py \
  --python-executable /usr/local/bin/python \
  --cddlib-source-archive /opt/provider/cddlib.tar.gz \
  --pycddlib-source-archive /opt/provider/pycddlib.tar.gz \
  --pin /app/pin.json \
  --output /app/evidence/provider-report.json
python /solution/solve.py
