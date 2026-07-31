FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact rational verifier for a piecewise-linear analysis construction.
LABEL jacobian.task="nondifferentiable-maximum-construction" \
      jacobian.checksum="c96e6a5f0a25095f11b36c78803fdf33d840a48580dd69a2c201804fc108362c"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "nondifferentiable-maximum-construction"'
