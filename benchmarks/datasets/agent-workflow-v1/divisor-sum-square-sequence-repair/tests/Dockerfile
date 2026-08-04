FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="c42531ca5887a2aae33fe19e7ee8eab3b40622717ca633204c16a14273684a9c"
LABEL jacobian.task="jacobian/divisor-sum-square-sequence-repair"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
