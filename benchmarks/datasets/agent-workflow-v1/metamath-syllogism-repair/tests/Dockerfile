FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="348d3ef544c6a08745feab408ce3fd767f37a32741020b93fca8a5baa4707997"
LABEL jacobian.task="jacobian/metamath-syllogism-repair"
COPY expected.json input.json test.sh verifier.py verifier_support.py proof_replay.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
