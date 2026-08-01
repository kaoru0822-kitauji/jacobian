FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="1ae70e40ee321b4e1796e6ceec21139c02252bde93e5f3b9d2674f3a1d2eb3ed"
LABEL jacobian.task="jacobian/agent-workflow-v1-lean-transitive-axiom-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/agent-workflow-v1-lean-transitive-axiom-audit"'
