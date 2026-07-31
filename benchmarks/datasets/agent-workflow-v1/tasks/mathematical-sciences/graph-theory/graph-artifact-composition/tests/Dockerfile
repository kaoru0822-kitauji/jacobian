FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
LABEL jacobian.task="jacobian/agent-workflow-v1-graph-artifact-composition" \
      jacobian.checksum="6159cc66a385ca6c87f0b6c514a239a1dbb26660785a71709f7e1652bd208051"
COPY expected.json agent-workflow-v1-graph-artifact-composition-input.json test.sh verifier.py verifier_support.py /tests/
COPY agent-workflow-v1-graph-artifact-composition-input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/agent-workflow-v1-graph-artifact-composition"'
