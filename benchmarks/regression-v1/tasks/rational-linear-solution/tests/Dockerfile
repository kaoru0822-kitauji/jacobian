FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
LABEL jacobian.task="rational-linear-solution" \
      jacobian.checksum="10807d714d10cc82248e76b814803fa053f1da2de2d9cca928d20901b0e3e998"
COPY . /tests
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
