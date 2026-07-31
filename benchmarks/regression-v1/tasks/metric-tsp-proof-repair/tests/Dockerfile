FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact finite optimization and proof-repair verifier.
LABEL jacobian.task="metric-tsp-proof-repair" \
      jacobian.checksum="305629fcfff29d001c1e31f0686e16ab0285d551b9dfb88bdbbc0b69ed715cca"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "metric-tsp-proof-repair"'
