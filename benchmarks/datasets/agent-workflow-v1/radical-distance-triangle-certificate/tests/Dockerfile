FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact verifier for a radical distance-model certificate.
LABEL jacobian.task="jacobian/radical-distance-triangle-certificate" \
      jacobian.checksum="6a1df316a4ab49161c33f8737bdd6c6d7e151af504eca15b39f3482d1f00d0d7"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/radical-distance-triangle-certificate"'
