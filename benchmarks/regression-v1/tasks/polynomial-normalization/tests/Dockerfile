FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Build context key: polynomial normalization.
LABEL jacobian.task="polynomial-normalization" \
      jacobian.checksum="94cdddd31d0e84c69218c4b5f92740d80b479c425782b55287bfdc3f63432d4b"
COPY authorized_record.json polynomial-normalization-expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/polynomial-normalization-expected.json"))["task_id"] == "polynomial-normalization"'
