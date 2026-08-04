FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="2b6cc916fc8f07e85f7a4c6207a9568bb5cb8e367fceb69b5bca8f64f261fd14"
LABEL jacobian.task="jacobian/metamath-syllogism-repair"
COPY expected.json input.json test.sh verifier.py verifier_support.py proof_replay.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
