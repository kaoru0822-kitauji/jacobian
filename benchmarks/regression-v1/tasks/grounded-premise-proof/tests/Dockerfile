FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Grounded premise-selection and proof-DAG verifier.
LABEL jacobian.task="grounded-premise-proof" \
      jacobian.checksum="1918ec605326bef844947999d3b599a95dde067dd6198c037aaf80991adb51c4"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "grounded-premise-proof"'
