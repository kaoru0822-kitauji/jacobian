FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
LABEL jacobian.task="graph-artifact-composition" \
      jacobian.checksum="e8c29d2e2bec1d07c9245854a1e68a9ed4fbec1fb809052f6b108484b236d943"
COPY . /tests
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
