FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="75889506fadecf68b763349737a4ca6cda849a063197a0f34244facdabfb8db8"
LABEL jacobian.task="jacobian/metamath-syllogism-repair"
COPY expected.json input.json test.sh verifier.py verifier_support.py proof_replay.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
