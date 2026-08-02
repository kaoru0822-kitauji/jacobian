FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="fdf79ea0ea55f03d32958461279484a82bbd107047c80f3f28b7e78fd87941f7"
LABEL jacobian.task="jacobian/inseparable-minimal-polynomial-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/inseparable-minimal-polynomial-audit"'
