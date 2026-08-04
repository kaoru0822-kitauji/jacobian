FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exhaustive finite-design verifier for a Steiner triple system.
LABEL jacobian.task="jacobian/steiner-triple-system-27" \
      jacobian.checksum="a07f10dba2ac3b6f8e2c3a7348654e869e94708978213bb6a6b8ba7cac282c2b"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/steiner-triple-system-27"'
