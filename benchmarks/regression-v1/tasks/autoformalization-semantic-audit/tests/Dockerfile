FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact semantic-alignment verifier for an autoformalized orthogonality claim.
LABEL jacobian.task="autoformalization-semantic-audit" \
      jacobian.checksum="eb44d9dfc9f239fab55166e8fd8b4f02ebb6ea82ed37198b1cb468f907785f31"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "autoformalization-semantic-audit"'
