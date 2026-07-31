FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact AST and rational linear-combination verifier for a proof repair.
LABEL jacobian.task="natural-subtraction-proof-repair" \
      jacobian.checksum="5e3c50bd6ba6e2c43293514cc44688132e0473b5879d0851686687309992d180"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "natural-subtraction-proof-repair"'
