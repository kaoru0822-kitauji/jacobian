FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact finite optimization and proof-repair verifier.
LABEL jacobian.task="jacobian/agent-workflow-v1-metric-tsp-proof-repair" \
      jacobian.checksum="2fb9e63837135360cab3a801658489cb80003ebf95311e3e084502aebada2737"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/agent-workflow-v1-metric-tsp-proof-repair"'
