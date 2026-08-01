FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="b0b3c3a024fdde1defc7e938b4b61560235289a3851ed6e5678f4554ccaf9ad9"
LABEL jacobian.task="jacobian/gaussian-moment-generality-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/gaussian-moment-generality-audit"'
