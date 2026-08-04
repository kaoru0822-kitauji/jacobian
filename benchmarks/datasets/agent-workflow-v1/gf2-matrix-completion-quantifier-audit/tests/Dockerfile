FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="db8e80163ec19fa56cf1a25f9ad183e5883b3ec7dc0f47f9f543782bed92e84d"
LABEL jacobian.task="jacobian/gf2-matrix-completion-quantifier-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
