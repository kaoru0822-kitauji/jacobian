FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="cbfd129b4f235c5d3500aa78cf8c1281192e2219d803fe7145b69a2a122722ca"
LABEL jacobian.task="jacobian/agent-workflow-v1-inverse-distance-remainder-audit" \
      jacobian.checksum="pending-harbor-sync"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/agent-workflow-v1-inverse-distance-remainder-audit"'
