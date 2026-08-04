FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact verifier for a two-tail Lp integrability construction.
LABEL jacobian.task="jacobian/lp-integrability-separator" \
      jacobian.checksum="3b94e296ebabd8cb55962cf0479e34caf2c4a1fb71812413db795724c4546a6f"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/lp-integrability-separator"'
