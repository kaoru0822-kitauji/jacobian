FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="e8928a3dcc8e479d09a4197ee06531d095f5bd7123fb1a931a49cd8844fd569d"
LABEL jacobian.task="jacobian/continuant-reversal-certificate"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/continuant-reversal-certificate"'
