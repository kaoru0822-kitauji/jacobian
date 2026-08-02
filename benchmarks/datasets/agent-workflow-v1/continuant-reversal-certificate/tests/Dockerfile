FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="29ddb26f24e905ebbc329081831db77bf10b3e3c610d8934854128fd4b280c97"
LABEL jacobian.task="jacobian/continuant-reversal-certificate"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/continuant-reversal-certificate"'
