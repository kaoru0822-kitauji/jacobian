FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact construction-witness verifier image.
LABEL jacobian.task="divisibility-construction-witness" \
      jacobian.checksum="65543bf1181bf1b1f4c0745f5fa8df711e7bb387a42cdd2d97aca170f1985900"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "divisibility-construction-witness"'
