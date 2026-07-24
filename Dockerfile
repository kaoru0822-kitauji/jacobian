FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY lean ./lean

RUN uv sync --locked --no-dev

EXPOSE 8000
VOLUME ["/var/lib/jacobian"]

ENTRYPOINT ["uv", "run", "--no-sync", "jacobian-mcp"]
CMD ["--help"]
