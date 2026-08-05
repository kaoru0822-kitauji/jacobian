FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exhaustive finite-design verifier for a Steiner triple system.
LABEL jacobian.task="jacobian/steiner-triple-system-27" \
      jacobian.checksum="14d5894293ed2a81ef7dfeab26f4972aff7d7e075e92be3da7dc4a17478cfac8"
COPY expected.json input.json test.sh verifier.py verifier_support.py public_contract.json /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/steiner-triple-system-27"'
