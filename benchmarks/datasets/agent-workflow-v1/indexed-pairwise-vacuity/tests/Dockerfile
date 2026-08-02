FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact verifier for indexed versus value-level pairwise semantics.
LABEL jacobian.task="jacobian/indexed-pairwise-vacuity" \
      jacobian.checksum="94d18c8bf609c8b56ecbba519918188192ffee889f6145d31d80db1d35e3e3f2"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/indexed-pairwise-vacuity"'
