FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact semantic-alignment verifier for an autoformalized orthogonality claim.
LABEL jacobian.task="autoformalization-semantic-audit" \
      jacobian.checksum="ff652ef066627c6eeac528077bd8369c56ff8ffa1110a01a4a6bd3394f0cefbf"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "autoformalization-semantic-audit"'
