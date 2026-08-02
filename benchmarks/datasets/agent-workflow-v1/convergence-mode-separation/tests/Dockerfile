FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact verifier for a dyadic convergence-mode separation certificate.
LABEL jacobian.task="jacobian/convergence-mode-separation" \
      jacobian.checksum="63ff67b19ed19ad6028a2069d937e60f9814d46a064feb429fcf8bfe374272f9"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/convergence-mode-separation"'
