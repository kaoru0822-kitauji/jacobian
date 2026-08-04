FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="69fd9539fe33ee4c9412585e99cca181347e3b8214e9bdd0e5cf94be9a7cd7f2"
LABEL jacobian.task="jacobian/divisor-sum-square-sequence-repair"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
