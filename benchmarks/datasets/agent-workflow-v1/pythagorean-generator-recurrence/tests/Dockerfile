FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact recurrence and quadratic-invariant verifier.
LABEL jacobian.task="jacobian/pythagorean-generator-recurrence" \
      jacobian.checksum="54ec00f6a79d5432264673604bf85724de99a7e5b073d548813b0a64d8c4d43f"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/pythagorean-generator-recurrence"'
