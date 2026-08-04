FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="99f0905f3f87d7417b4eaa9bcfd3a59855cd214aa3ae0da1cce6b5d714ea8a0b"
LABEL jacobian.task="jacobian/gf2-matrix-completion-quantifier-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
