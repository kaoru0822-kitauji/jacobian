FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="2614e5afa46033224f6bb7e6b9a688a1ddcb99dc4ac41ebab013794201622cba"
LABEL jacobian.task="jacobian/agent-workflow-v1-generated-lemma-vacuity-audit" \
      jacobian.checksum="pending-harbor-sync"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/agent-workflow-v1-generated-lemma-vacuity-audit"'
