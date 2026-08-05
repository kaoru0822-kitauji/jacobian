FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="1429af7a335e8754d40bc41b0016822be298a5a686c0fe606a288e91b11f2fa3"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
RUN chmod +x /tests/test.sh
