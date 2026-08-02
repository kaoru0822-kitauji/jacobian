FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="9345d4d467d8afe0a410914a11ffa276ac5c899ef8443a946ee198cf9379c060"
LABEL jacobian.task="jacobian/symmetric-polynomial-divisibility"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
