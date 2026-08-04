FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
LABEL jacobian.checksum="52017a8eb820865a1ea4d1bd0d139b2a0f8a697f612b6b44b3dbb3f497f7d054"
# Exact verifier for bounded-variation uniform-limit certificates.
LABEL jacobian.task="jacobian/bounded-variation-uniform-limit"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
