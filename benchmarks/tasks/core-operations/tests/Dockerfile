FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="2893a5a94652951ceb45e9828da9a4180d3a41b64f2dbf8ba6dede298c908347"
COPY expected.json test.sh verifier.py verifier_support.py /tests/
RUN chmod +x /tests/test.sh
