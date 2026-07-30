FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
LABEL jacobian.task="sat-witness" \
      jacobian.checksum="16d7841bb53b7596c9519486af39da33dbf115a1344316baf2bc10bbd82cdfa2"
COPY . /tests
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
