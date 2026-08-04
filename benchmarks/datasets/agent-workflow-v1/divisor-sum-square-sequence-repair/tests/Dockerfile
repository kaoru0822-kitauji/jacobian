FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="9ee5affd3dd0e0289091eeafbe04f94f6281a4a65e8c8cbaf037038675c49df2"
LABEL jacobian.task="jacobian/divisor-sum-square-sequence-repair"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
