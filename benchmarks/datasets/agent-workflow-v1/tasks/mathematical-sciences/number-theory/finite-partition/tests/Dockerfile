FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
LABEL jacobian.task="jacobian/agent-workflow-v1-finite-partition" \
      jacobian.checksum="70e1273c9e29f66f5870d036f3cc3d6456db7ba112081b2a87008d5e4d7b159a"
COPY authorized_record.json expected.json agent-workflow-v1-finite-partition-input.json test.sh verifier.py verifier_support.py /tests/
COPY agent-workflow-v1-finite-partition-input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/agent-workflow-v1-finite-partition"'
