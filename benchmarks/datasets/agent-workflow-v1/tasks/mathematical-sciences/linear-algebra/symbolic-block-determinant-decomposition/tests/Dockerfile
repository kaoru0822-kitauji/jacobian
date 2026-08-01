FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="27402dc84c3e5dacca84fb75f81bcd800421f1c136508a64357c7d66c9957067"
LABEL jacobian.task="jacobian/agent-workflow-v1-symbolic-block-determinant-decomposition"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
