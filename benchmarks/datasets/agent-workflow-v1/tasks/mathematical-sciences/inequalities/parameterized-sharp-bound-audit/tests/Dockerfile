FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="c52494d738f14b5ac3acc8a2c2e7316f3fc7006f7076b241a309ce7b2c69367f"
LABEL jacobian.task="jacobian/agent-workflow-v1-parameterized-sharp-bound-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/agent-workflow-v1-parameterized-sharp-bound-audit"'
