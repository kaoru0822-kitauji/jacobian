FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="2346ae96874fe696c1b13593fdada67e6e47dad21fcce27993aaa7a4aae75c16"
LABEL jacobian.task="jacobian/lean-guard-scope-assurance"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/lean-guard-scope-assurance"'
