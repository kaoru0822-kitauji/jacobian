FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
LABEL jacobian.task="jacobian/agent-workflow-v1-hermite-normal-form" \
      jacobian.checksum="3ad621d0bf797924d2b09dc2d5f895785278fb2b4f67d5c1d2b05b0a1e229245"
COPY authorized_record.json expected.json agent-workflow-v1-hermite-normal-form-input.json test.sh verifier.py verifier_support.py /tests/
COPY agent-workflow-v1-hermite-normal-form-input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/agent-workflow-v1-hermite-normal-form"'
