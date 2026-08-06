FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="3d50f293af713b8e09b3fda0c9331ea5487dd73096ab20372d7ff9c8d58c50fe"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
RUN chmod +x /tests/test.sh
