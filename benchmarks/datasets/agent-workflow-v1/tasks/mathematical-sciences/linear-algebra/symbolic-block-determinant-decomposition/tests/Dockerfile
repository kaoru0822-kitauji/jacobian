FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="e9eadf2d116cdb2d094d55d195faf47b1f56f7dcb818e5f997c73ce0366cefff"
LABEL jacobian.task="jacobian/agent-workflow-v1-symbolic-block-determinant-decomposition"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
