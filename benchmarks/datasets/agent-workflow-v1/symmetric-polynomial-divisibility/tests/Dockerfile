FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="6cb6520a6cba7d7f60740d843181d9f8a15c02c5e3240543e371955434090cad"
LABEL jacobian.task="jacobian/symmetric-polynomial-divisibility"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
