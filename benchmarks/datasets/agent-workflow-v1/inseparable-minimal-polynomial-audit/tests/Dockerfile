FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="77d049c783d6b81d5b50c5f7de5260f33de3ac58ed82733d82800a170c694a2f"
LABEL jacobian.task="jacobian/inseparable-minimal-polynomial-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/inseparable-minimal-polynomial-audit"'
