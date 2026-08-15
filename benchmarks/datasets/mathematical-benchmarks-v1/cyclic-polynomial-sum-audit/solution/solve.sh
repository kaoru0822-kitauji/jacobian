#!/bin/sh
set -eu
mkdir -p /app/evidence
cp /solution/submission.json /app/submission.json
cp /solution/cyclic-elimination-certificate.json /app/evidence/cyclic-elimination-certificate.json
