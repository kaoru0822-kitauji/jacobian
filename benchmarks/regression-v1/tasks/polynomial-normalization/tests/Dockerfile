FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
LABEL jacobian.task="polynomial-normalization" \
      jacobian.checksum="5754c12d562c55973863861015fb9f9e9bada9736b6059807552ad633ea954a1"
COPY . /tests
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
