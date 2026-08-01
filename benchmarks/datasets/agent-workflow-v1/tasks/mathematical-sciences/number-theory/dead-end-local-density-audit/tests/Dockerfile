FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="ba510df2558f30648cce826d27842081c7b8eccbde425a3431e42af2f4107ee9"
LABEL jacobian.task="jacobian/agent-workflow-v1-dead-end-local-density-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/agent-workflow-v1-dead-end-local-density-audit"'
