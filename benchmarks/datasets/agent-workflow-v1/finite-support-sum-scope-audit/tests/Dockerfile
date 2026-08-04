FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="82fd593c505d9f4eb5dadc9fefaf611026b89e8be01db743adfd8a27f573469a"
LABEL jacobian.task="jacobian/finite-support-sum-scope-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py public_contract.json /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
