FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="2ffb96f45a9e5edcba1222a48719f38847ba8f4f5f83874ce4b0e043b0cce9e7"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
RUN chmod +x /tests/test.sh
