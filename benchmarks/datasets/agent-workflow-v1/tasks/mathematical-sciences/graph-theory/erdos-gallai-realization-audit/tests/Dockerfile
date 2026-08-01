FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="689c60dd527f05de76335560151b862ba9865d9727eb9f8fb9d538d349b3c664"
LABEL jacobian.task="jacobian/agent-workflow-v1-erdos-gallai-realization-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/agent-workflow-v1-erdos-gallai-realization-audit"'
