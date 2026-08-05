FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="0f2356dd4644b3a226cc2ac0469cba8c8a11cde2309533866cff89c90e75508e"
COPY verifier.py verifier_support.py input.json test.sh /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
