FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates git && \
    rm -rf /var/lib/apt/lists/*
RUN git init /opt/jacobian && \
    git -C /opt/jacobian remote add origin https://github.com/morluto/jacobian.git && \
    git -C /opt/jacobian fetch --depth 1 origin 6fd5fc5df6bc49f230484bc5c78cbd365941c78c && \
    git -C /opt/jacobian checkout --detach FETCH_HEAD && \
    uv sync --project /opt/jacobian --locked --dev
WORKDIR /app
COPY benchmark.py input.json submission_schema.json /app/
ENV PYTHONDONTWRITEBYTECODE=1
