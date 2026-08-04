FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact verifier for a pointwise inversion-definition audit.
LABEL jacobian.task="jacobian/inversion-aggregate-mask-audit" \
      jacobian.checksum="8a58d57cf56c9187e41a53a986dc20d97bcdb9a289009c13689a3e02595f8f17"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/inversion-aggregate-mask-audit"'
