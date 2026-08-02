FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="5ae856eb43e945473cd86a3420049eb733ae8211cfe2c2ca2e295f2f7fbfdbb4"
LABEL jacobian.task="jacobian/exponential-moment-rationality"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
