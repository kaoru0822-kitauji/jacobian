FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="d6d3e9aaa5015d1f8e43d47a2b298b769a76f19e4eabeaea820d5d59c5f15d6e"
LABEL jacobian.task="jacobian/rsa-exponent-domain-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py public_contract.json /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/rsa-exponent-domain-audit"'
