FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="6d532271ce1677e29bb6e588abdd974cd05a48416eea3cecc77e5b156eeb69eb"
LABEL jacobian.task="jacobian/gf2-matrix-completion-quantifier-audit"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
