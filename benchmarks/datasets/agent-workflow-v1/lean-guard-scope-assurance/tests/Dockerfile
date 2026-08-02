FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="bf3bc8af60c7ee05ce04d873c8075a6be181e9ca7b786332781ce284533d9008"
LABEL jacobian.task="jacobian/lean-guard-scope-assurance"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/lean-guard-scope-assurance"'
