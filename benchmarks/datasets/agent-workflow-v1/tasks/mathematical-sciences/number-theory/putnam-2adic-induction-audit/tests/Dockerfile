FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="4da97ecb73e0832fbff5bde363b9114a7a0724e5ec35eeaa96b5befc84d2e9f7"
LABEL jacobian.task="jacobian/agent-workflow-v1-putnam-2adic-induction-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/agent-workflow-v1-putnam-2adic-induction-audit"'
