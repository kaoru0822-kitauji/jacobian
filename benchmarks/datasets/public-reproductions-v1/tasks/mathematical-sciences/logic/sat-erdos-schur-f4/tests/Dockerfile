FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
LABEL jacobian.task="jacobian/public-reproductions-v1-sat-erdos-schur-f4" \
      jacobian.checksum="978bf6be5f21850619f8330316911b2132784762f249a4f1c01d909e1db3b815"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/public-reproductions-v1-sat-erdos-schur-f4"'
