FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.task="jacobian/vizing-bounded-cartesian-products" \
      jacobian.checksum="e84a60b16b14a75626d98e57fbb89a26dd2081d47c27418c41581dd40bc89963"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && python -c 'import json; assert json.load(open("/tests/input.json"))["task_id"] == "jacobian/vizing-bounded-cartesian-products"'
