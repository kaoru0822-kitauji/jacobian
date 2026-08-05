FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="e29629f35ec8146697ae24f35baa951fcee3568ba89c88261d5725e859e833c0"
LABEL jacobian.task="jacobian/sine-integral-asymptotic-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/sine-integral-asymptotic-audit"'
