FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="ca5865d2ff5e82c1142aec0fd0fae20d109559cd2301eed99e161c6f1982a282"
LABEL jacobian.task="jacobian/divisor-sum-square-sequence-repair"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
