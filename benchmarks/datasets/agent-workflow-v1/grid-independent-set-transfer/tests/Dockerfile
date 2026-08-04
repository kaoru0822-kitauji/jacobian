FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="e8a59d2c8bea7d23275c32ae4aa1babbe6c08ccd3cc7957df7529a90943128fb"
COPY verifier.py verifier_support.py input.json expected.json test.sh /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/grid-independent-set-transfer"'
