FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact verifier for image/complement commutation conformance.
LABEL jacobian.task="jacobian/image-complement-commutation" \
      jacobian.checksum="014dff5d08bacfbabb44de6a8bd7da443bbf61db4891ee070ab465a042d04e61"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/image-complement-commutation"'
