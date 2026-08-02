FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact radical-elimination audit verifier.
LABEL jacobian.task="jacobian/radical-system-uniqueness-audit" \
      jacobian.checksum="7e68ea95485bc38784cb663cd97b38895ffbf500a5895f49cdee0bbda53c3b5b"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/radical-system-uniqueness-audit"'
