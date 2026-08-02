FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="d8aa1a6354047f6c10dd60f578dd2fb3364a8c2508c12e582652ecb49197e725"
LABEL jacobian.task="jacobian/polynomial-divisibility-uniqueness"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/polynomial-divisibility-uniqueness"'
