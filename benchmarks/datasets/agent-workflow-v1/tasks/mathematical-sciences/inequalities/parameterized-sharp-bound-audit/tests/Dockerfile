FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="f0b73c23feb1814ac9613af826cc714cbac8bb4056aa8ac61bb93f1ac9b4f850"
LABEL jacobian.task="jacobian/agent-workflow-v1-parameterized-sharp-bound-audit" \
      jacobian.checksum="pending-harbor-sync"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/agent-workflow-v1-parameterized-sharp-bound-audit"'
