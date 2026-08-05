FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exhaustive finite-design verifier for a Steiner triple system.
LABEL jacobian.task="jacobian/steiner-triple-system-27" \
      jacobian.checksum="1795e360afa64b32fa6c1c2c40d41a4ec906d1dd8c2f1883bd0ac9a1f96eb53d"
COPY expected.json input.json test.sh verifier.py verifier_support.py public_contract.json /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/steiner-triple-system-27"'
