FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exhaustive finite-design verifier for a Steiner triple system.
LABEL jacobian.task="jacobian/steiner-triple-system-27" \
      jacobian.checksum="49a61daf42416dc6a96bbc33633943c0ac91d5f5c2273639b910df5a6f162287"
COPY expected.json input.json test.sh verifier.py verifier_support.py public_contract.json /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/steiner-triple-system-27"'
