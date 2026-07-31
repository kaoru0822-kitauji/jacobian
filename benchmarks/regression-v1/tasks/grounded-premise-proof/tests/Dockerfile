FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Grounded premise-selection and proof-DAG verifier.
LABEL jacobian.task="grounded-premise-proof" \
      jacobian.checksum="0d04e61164092d73e60c525b4ad7847bfc45c88a5f63d60ce23feeb67ccbeb8c"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "grounded-premise-proof"'
