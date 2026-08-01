FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="a86f52d56ba9bff976ff4767f137b6acbd7fb33e37301cce7ae47c55adbea0dd"
LABEL jacobian.task="jacobian/agent-workflow-v1-lcm-highly-abundant-scope-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/agent-workflow-v1-lcm-highly-abundant-scope-audit"'
