FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="d3e831f45e38693a2f66867639eb3ba42cf90fb89c2e3511ca5492b2af99995f"
LABEL jacobian.task="jacobian/trigonometric-power-sum-valuation"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/trigonometric-power-sum-valuation"'
