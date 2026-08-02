FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="04c36cfaeede1d94afe7ce20eaa29099019c622eb7db3bca3c9d81594588401a"
LABEL jacobian.task="jacobian/inseparable-minimal-polynomial-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/inseparable-minimal-polynomial-audit"'
