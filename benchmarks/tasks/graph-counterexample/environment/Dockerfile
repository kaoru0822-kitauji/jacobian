FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

ARG CODEX_VERSION=0.146.0
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG http_proxy
ARG https_proxy
ARG no_proxy

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        nodejs \
        npm \
        ripgrep \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --global "@openai/codex@${CODEX_VERSION}" \
    && codex --version

WORKDIR /app
COPY input.json submission_schema.json /app/
ENV PYTHONDONTWRITEBYTECODE=1
