FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
LABEL jacobian.task="polynomial-map-collision" \
      jacobian.checksum="2a3a4449f2acddd389cf689ac6305054b28011190f59e94a704f2fc0bb9a3ddd"
COPY . /tests
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
