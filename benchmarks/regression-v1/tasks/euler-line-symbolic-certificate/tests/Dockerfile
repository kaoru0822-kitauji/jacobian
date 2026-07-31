FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact sparse rational-function identity verifier.
LABEL jacobian.task="euler-line-symbolic-certificate" \
      jacobian.checksum="33b491a1bd2f5367883577545165d0b6f4d3a27cdee12d2f2f566cd5474748f0"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "euler-line-symbolic-certificate"'
