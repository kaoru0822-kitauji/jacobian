FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact positive-lower-density separation verifier.
LABEL jacobian.task="jacobian/positive-lower-density-separation" \
      jacobian.checksum="3970f10c82f303e0c61aa74d52f0764bf660ab28e3d96a979f716b3762f581a6"
RUN python -m pip install --no-cache-dir attrs==26.1.0 jsonschema==4.26.0 jsonschema-specifications==2025.9.1 referencing==0.37.0 rpds-py==2026.6.3 typing-extensions==4.16.0
COPY expected.json input.json test.sh verifier.py verifier_support.py public_contract.json verifier_contract.json /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
