FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
LABEL jacobian.checksum="eed9b39aae4d44f6ee6d3d71fb05afa956347fb160c0418a6ff81cdaec8f767c"
# Exact verifier for bounded-variation uniform-limit certificates.
LABEL jacobian.task="jacobian/bounded-variation-uniform-limit"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
