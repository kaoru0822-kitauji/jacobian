FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.task="jacobian/vizing-bounded-cartesian-products" \
      jacobian.checksum="a3eef8a8d1e9ee70933dbf39213aec47bc41d155e7d21f44c7b16697e7e76e78"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && python -c 'import json; assert json.load(open("/tests/input.json"))["task_id"] == "jacobian/vizing-bounded-cartesian-products"'
