FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="e5e44393e0871d8a1bc3d89c852701da654a750d74a870fc70e19279a3b6f94f"
LABEL jacobian.task="jacobian/agent-workflow-v1-noncompact-lefschetz-proof-audit" \
      jacobian.checksum="pending-harbor-sync"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/agent-workflow-v1-noncompact-lefschetz-proof-audit"'
