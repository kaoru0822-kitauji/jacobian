FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="f068be9b0c5f2ccd959fa34ab91f6bb704e988737fbf823c683d0e9788a200cb"
LABEL jacobian.task="jacobian/diophantine-ratio-family-repair"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/diophantine-ratio-family-repair"'
