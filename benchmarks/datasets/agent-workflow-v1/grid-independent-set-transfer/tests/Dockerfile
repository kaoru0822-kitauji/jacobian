FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="2b9da86e8e70953a00425d44e726ac1c161ea4f727750d7febcd9e6fab2df1df"
COPY verifier.py verifier_support.py input.json expected.json test.sh /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/grid-independent-set-transfer"'
