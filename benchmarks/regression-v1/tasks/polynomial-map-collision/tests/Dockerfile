FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
LABEL jacobian.task="polynomial-map-collision" \
      jacobian.checksum="9104ed5b43837c129adb5d017428949325e0e3d957a06bc639447fb533d4c587"
COPY authorized_record.json polynomial-map-collision-expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/polynomial-map-collision-expected.json"))["task_id"] == "polynomial-map-collision"'
