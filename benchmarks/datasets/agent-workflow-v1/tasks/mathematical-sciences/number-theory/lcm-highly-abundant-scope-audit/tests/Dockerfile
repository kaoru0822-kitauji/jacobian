FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="45f5f70282f4175e78213ea89a72ed1172ee65c19ccea73f1c990099b607ec32"
LABEL jacobian.task="jacobian/agent-workflow-v1-lcm-highly-abundant-scope-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/agent-workflow-v1-lcm-highly-abundant-scope-audit"'
