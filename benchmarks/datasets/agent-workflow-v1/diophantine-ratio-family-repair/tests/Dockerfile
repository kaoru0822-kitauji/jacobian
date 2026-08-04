FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="928bccdd80285bf7fa6813d5ee0755ff08abb50de47879e1849911688ad9ce98"
LABEL jacobian.task="jacobian/diophantine-ratio-family-repair"
COPY expected.json input.json test.sh verifier.py verifier_support.py public_contract.json /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/diophantine-ratio-family-repair"'
