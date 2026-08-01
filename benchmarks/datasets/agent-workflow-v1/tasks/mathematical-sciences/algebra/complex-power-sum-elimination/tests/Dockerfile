FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="cc7b3b91ca05da1845a50ee36d606be4be440f6cca4160289600bc10563d2ad2"
LABEL jacobian.task="jacobian/agent-workflow-v1-complex-power-sum-elimination" \
      jacobian.checksum="pending-harbor-sync"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/agent-workflow-v1-complex-power-sum-elimination"'
