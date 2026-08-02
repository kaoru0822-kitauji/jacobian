FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
LABEL jacobian.task="jacobian/graph-atlas-enumeration" \
      jacobian.checksum="847b3ffb9d668e28aa4bb1e6ccf0559bf6ab6062b09716b70a7f4c5f5c9ec9c8"
COPY expected.json agent-workflow-v1-graph-atlas-enumeration-input.json test.sh verifier.py verifier_support.py /tests/
COPY agent-workflow-v1-graph-atlas-enumeration-input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/graph-atlas-enumeration"'
