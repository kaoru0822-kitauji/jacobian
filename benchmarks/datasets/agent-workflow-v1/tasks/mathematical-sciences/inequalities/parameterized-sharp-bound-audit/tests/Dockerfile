FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="5bb05ef93011e53314c4884d9b8b8aa32bf0198fb815c06a0dd91ce84c771d3a"
LABEL jacobian.task="jacobian/agent-workflow-v1-parameterized-sharp-bound-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/agent-workflow-v1-parameterized-sharp-bound-audit"'
