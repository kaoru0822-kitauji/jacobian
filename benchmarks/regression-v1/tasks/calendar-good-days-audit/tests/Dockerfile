FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Bounded exhaustive audit verifier.
LABEL jacobian.task="calendar-good-days-audit" \
      jacobian.checksum="7717db7c153b80e3bf3607a0c58c342eabc1fae9f754cf1bdda44d3901040bb4"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "calendar-good-days-audit"'
