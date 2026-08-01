FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exhaustive finite optimizer for canonical distinct-sum pairings.
LABEL jacobian.task="jacobian/distinct-sum-pairing-optimum" \
      jacobian.checksum="b5a93735b50df9fe00bb5f9001017612c3a73ffe18bc007978adcfb44e5ce28d"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/distinct-sum-pairing-optimum"'
