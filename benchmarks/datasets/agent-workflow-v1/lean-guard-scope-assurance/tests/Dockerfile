FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="9ab9a628ec3f53954105cd9b1d4f0a3888b00ab555a7b54472c565771aeadfef"
LABEL jacobian.task="jacobian/putnam-2adic-induction-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/putnam-2adic-induction-audit"'
