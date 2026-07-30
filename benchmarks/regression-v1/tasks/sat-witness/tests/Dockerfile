FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
LABEL jacobian.task="sat-witness" \
      jacobian.checksum="7e5ef9d611b0b6b524b05878b3c5b29338ebbca22de8a358cd35bfaeb951ae10"
COPY authorized_records.json expected.json sat-witness-input.json test.sh verifier.py verifier_support.py /tests/
COPY sat-witness-input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "sat-witness"'
