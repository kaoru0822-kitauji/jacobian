FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="9b5e8a1cae9fb3b1f79dbabbd9d72f15506511933e1c705e053ead33fe516e53"
LABEL jacobian.task="jacobian/agent-workflow-v1-euler-fourth-power-scope-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/agent-workflow-v1-euler-fourth-power-scope-audit"'
