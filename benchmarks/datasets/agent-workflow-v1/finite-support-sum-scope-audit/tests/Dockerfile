FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="816ec92e277e598a4a85527ef728de77005a88fcf69f42576aec1ed274021980"
LABEL jacobian.task="jacobian/finite-support-sum-scope-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
