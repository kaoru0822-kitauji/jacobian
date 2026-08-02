FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="e1891e8ee3438ffd8623051af452671f2edb86acbf87e7683b47bbff47a6c07d"
LABEL jacobian.task="jacobian/trigonometric-power-sum-valuation"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/trigonometric-power-sum-valuation"'
