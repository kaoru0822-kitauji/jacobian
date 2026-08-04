FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
LABEL jacobian.checksum="4f980bddeae658a27116f6663b248c3342d07738ad1a878dfcf6c525ed8c0e61"
# Exact verifier for bounded-variation uniform-limit certificates.
LABEL jacobian.task="jacobian/bounded-variation-uniform-limit"
COPY expected.json input.json test.sh verifier.py verifier_support.py public_contract.json /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
