FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
LABEL jacobian.task="hermite-normal-form" \
      jacobian.checksum="b817552b45ff49d3585ccfdc064bc4a3c0fbdc3e2242a313cb854df1f92f6e3b"
COPY . /tests
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
