FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Frozen citation-support audit verifier.
LABEL jacobian.task="jacobian/research-status-evidence-audit" \
      jacobian.checksum="bbfe7174c7127fee791c7231de0ca712ce767a2b3fa0d3e54a4780d4d1d9f861"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/research-status-evidence-audit"'
