FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="e839996e1e4664d0ec00d7be5a9bfebe45e3393554e89a4d8f4ec999e20bb125"
LABEL jacobian.task="jacobian/exponential-moment-rationality"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
