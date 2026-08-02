FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="231700b594767144d368721e10631ab2f7a168a867d27ec73606bb9ed872283e"
LABEL jacobian.task="jacobian/symmetric-polynomial-divisibility"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
