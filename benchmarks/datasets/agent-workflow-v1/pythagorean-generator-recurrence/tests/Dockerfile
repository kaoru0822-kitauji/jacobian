FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact recurrence and quadratic-invariant verifier.
LABEL jacobian.task="jacobian/pythagorean-generator-recurrence" \
      jacobian.checksum="0272093af558a90ff3ce43bcf11a37b13bf21121d1e6bd2091683c9ddcbfb0f2"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/pythagorean-generator-recurrence"'
