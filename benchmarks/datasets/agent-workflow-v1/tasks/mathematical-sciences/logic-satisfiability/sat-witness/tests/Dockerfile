FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
LABEL jacobian.task="jacobian/agent-workflow-v1-sat-witness" \
      jacobian.checksum="7ea84e98adedf1eb966269b5ae9f6402c24febe6571b523432efe10ccbc5e9c8"
COPY authorized_records.json expected.json agent-workflow-v1-sat-witness-input.json test.sh verifier.py verifier_support.py /tests/
COPY agent-workflow-v1-sat-witness-input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/agent-workflow-v1-sat-witness"'
