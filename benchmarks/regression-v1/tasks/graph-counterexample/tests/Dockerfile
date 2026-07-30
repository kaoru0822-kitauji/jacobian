FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
LABEL jacobian.task="graph-counterexample" \
      jacobian.checksum="041268a6113daf42cc5294889e60c02b7a1738bed5768dbbe9db5ed4aaaf9a3c"
COPY . /tests
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
