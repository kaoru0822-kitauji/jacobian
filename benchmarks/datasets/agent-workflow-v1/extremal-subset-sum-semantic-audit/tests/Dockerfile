FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact finite semantic verifier for binder shadowing and subset-sum drift.
LABEL jacobian.task="jacobian/extremal-subset-sum-semantic-audit" \
      jacobian.checksum="64fcf220da848a3ae33c45f3cfe94ab958eead1564adaa6ebe8990487f914650"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/extremal-subset-sum-semantic-audit"'
