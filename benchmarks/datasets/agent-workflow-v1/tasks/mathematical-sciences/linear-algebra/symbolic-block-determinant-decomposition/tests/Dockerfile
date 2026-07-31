FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="586a796b8d9757e8873f0a966239406360533d837b51790fad227c9bc57e7f29"
LABEL jacobian.task="jacobian/agent-workflow-v1-symbolic-block-determinant-decomposition" jacobian.checksum="pending-harbor-sync"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
