FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="2aa4f10c8ac2f0ae28f082123adb0761ce7fc9308192a889293587132428593c"
LABEL jacobian.task="jacobian/agent-workflow-v1-complex-power-sum-elimination"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/agent-workflow-v1-complex-power-sum-elimination"'
