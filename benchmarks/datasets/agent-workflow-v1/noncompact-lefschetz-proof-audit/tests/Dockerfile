FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="9afe74f7f1704b526838479d4b18d0d3d535565ff8b131c6f15cb37762b359b6"
LABEL jacobian.task="jacobian/noncompact-lefschetz-proof-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py public_contract.json /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/noncompact-lefschetz-proof-audit"'
