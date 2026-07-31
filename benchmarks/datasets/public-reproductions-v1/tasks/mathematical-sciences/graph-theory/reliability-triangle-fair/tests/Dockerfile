FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
LABEL jacobian.task="jacobian/public-reproductions-v1-reliability-triangle-fair" \
      jacobian.checksum="939fd892f97c2f8db0e2e6caa6720e483df4ebb034a49b94b0a716b6ea3bbe3f"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/public-reproductions-v1-reliability-triangle-fair"'
