FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Layered mathematical and rubric-audit verifier.
LABEL jacobian.task="log-inequality-meta-audit" \
      jacobian.checksum="08a9f88a4e7c4289a53eedb37fb5d81cbdc07581927fcea700a85717f8d8ec61"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "log-inequality-meta-audit"'
