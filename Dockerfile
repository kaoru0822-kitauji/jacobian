FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY lean ./lean

RUN uv sync --locked --no-dev --extra flint --extra smt

EXPOSE 8000
VOLUME ["/var/lib/jacobian"]

# Keep the default state root on the declared persistent volume.
ENV JACOBIAN_STATE_DIR=/var/lib/jacobian

ENTRYPOINT ["uv", "run", "--no-sync", "jacobian-mcp"]
CMD ["--help"]
