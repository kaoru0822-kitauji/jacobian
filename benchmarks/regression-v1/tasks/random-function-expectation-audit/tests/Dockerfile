FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact dependence-aware expectation verifier.
LABEL jacobian.task="random-function-expectation-audit" \
      jacobian.checksum="a105b862b56c7feffa7de328fff2bb6a3d196696d9512156d5e67afd2d6ab687"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "random-function-expectation-audit"'
