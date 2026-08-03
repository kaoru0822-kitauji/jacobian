#!/bin/sh
set -eu
mkdir -p /app/evidence
cp /solution/submission.json /app/submission.json
cp /solution/independence-certificate.json /app/evidence/independence-certificate.json
