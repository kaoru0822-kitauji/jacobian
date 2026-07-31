FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
LABEL jacobian.task="jacobian/public-reproductions-v1-recurrence-linear-eval" \
      jacobian.checksum="1dca9dd75e0ed87a76f3f76c3dbe91c68dcaa13e8dbb6ad39f4c6b930cef17c1"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/public-reproductions-v1-recurrence-linear-eval"'
