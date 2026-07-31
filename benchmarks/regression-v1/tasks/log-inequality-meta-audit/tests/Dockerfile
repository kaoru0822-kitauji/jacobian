FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Layered mathematical and rubric-audit verifier.
LABEL jacobian.task="log-inequality-meta-audit" \
      jacobian.checksum="1e5efffa2e536e54a656cefb1701957b028360044874a6d82be3394d96528c82"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "log-inequality-meta-audit"'
