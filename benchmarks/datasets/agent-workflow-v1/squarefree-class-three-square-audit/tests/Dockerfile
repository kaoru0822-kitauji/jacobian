FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="19d693cd5946e21fca51c8b6bf07500db0d567207a95d7ba446acbe68431b000"
LABEL jacobian.task="jacobian/squarefree-class-three-square-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/squarefree-class-three-square-audit"'
