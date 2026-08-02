FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="3c47f97b38c8856bce68a21e56f9a58deec4f7020a88b7d6ee88a94946ab83c8"
LABEL jacobian.checksum="placeholder"
LABEL jacobian.task="jacobian/exponential-moment-rationality"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
