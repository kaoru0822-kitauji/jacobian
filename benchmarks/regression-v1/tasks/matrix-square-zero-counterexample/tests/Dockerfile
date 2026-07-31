FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
LABEL jacobian.task="matrix-square-zero-counterexample" \
      jacobian.checksum="e4f3d0d6137112db167f034f478f2ede32ae2d53ae6733cd38f6f0da5ebb2b1c"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "matrix-square-zero-counterexample"'
