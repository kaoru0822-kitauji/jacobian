FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="d936d3796cafc0f730148fe99cd4d2e1207fd4a9b0be2b7b602932b6cd0e033c"
LABEL jacobian.task="jacobian/dead-end-local-density-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py public_contract.json /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/dead-end-local-density-audit"'
