FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
LABEL jacobian.task="jacobian/graph-atlas-enumeration" \
      jacobian.checksum="c0972b525167dc72accfe04815131bcdc2babaa5ad45d69d49c360d95a44e7a4"
COPY expected.json agent-workflow-v1-graph-atlas-enumeration-input.json test.sh verifier.py verifier_support.py /tests/
COPY agent-workflow-v1-graph-atlas-enumeration-input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/graph-atlas-enumeration"'
