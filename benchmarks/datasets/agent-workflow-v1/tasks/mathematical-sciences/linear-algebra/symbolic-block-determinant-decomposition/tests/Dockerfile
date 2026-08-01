FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="9331521a1716ceaa229bfbc0a25181f7e7dcb0651ce879525d23b3c52720f15d"
LABEL jacobian.task="jacobian/agent-workflow-v1-symbolic-block-determinant-decomposition" jacobian.checksum="pending-harbor-sync"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
