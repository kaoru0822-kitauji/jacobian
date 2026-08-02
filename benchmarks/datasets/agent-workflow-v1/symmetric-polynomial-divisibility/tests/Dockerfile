FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="40821aff15511fd666b14bd850f3e5612be3ad5a47e88eaa9df8c3a9c45caaf6"
LABEL jacobian.task="jacobian/symmetric-polynomial-divisibility"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
