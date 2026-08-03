FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Finite graph-cover path-lifting verifier.
LABEL jacobian.task="jacobian/covering-path-lift-bijection" \
      jacobian.checksum="1dfdcc28e747b12151b245e48583dd9b9faa7d2f60856350445389c0d2796bf6"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/covering-path-lift-bijection"'
