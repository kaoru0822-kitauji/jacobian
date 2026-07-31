FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact semantic-alignment verifier for an autoformalized orthogonality claim.
LABEL jacobian.task="autoformalization-semantic-audit" \
      jacobian.checksum="4ebf2702600c90bc5398bafce24c09435bfcafd3b235a7e0c3009df29d77ca07"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "autoformalization-semantic-audit"'
