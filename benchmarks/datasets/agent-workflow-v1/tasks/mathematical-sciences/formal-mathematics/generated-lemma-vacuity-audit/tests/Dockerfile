FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="233f4ed8c3cbdcceca8ca83cb5af1a3db581e0b05602daf240e02003266b1068"
LABEL jacobian.task="jacobian/agent-workflow-v1-generated-lemma-vacuity-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/agent-workflow-v1-generated-lemma-vacuity-audit"'
