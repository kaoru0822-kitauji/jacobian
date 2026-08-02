FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="ee028f20bc98164a1e2a67e669a685d9f26730dc21c09a65d2eaa77ab9c75e6a"
LABEL jacobian.task="jacobian/subset-incidence-determinant"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/subset-incidence-determinant"'
