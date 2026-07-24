# Deploy the remote MCP server

[Documentation home](../index.md)

Use STDIO for a single local Codex process. Use Streamable HTTP when ChatGPT or
another remote MCP client must reach Jacobian.

## Create the auth secret

Create a JSON file outside the repository:

```json
{
  "tokens": [
    {
      "tenant_id": "research-team-a",
      "token": "replace-with-at-least-32-random-characters",
      "scopes": ["jacobian:use"]
    }
  ]
}
```

Treat this as a secret. Rotate a token by replacing the file and restarting the
server. Do not put tokens in prompts, source control, command-line arguments,
or Jacobian artifacts.

## Start Streamable HTTP

```sh
uv run jacobian-mcp \
  --transport streamable-http \
  --tool-profile capabilities \
  --host 127.0.0.1 \
  --port 8000 \
  --path /mcp \
  --state-dir /var/lib/jacobian \
  --auth-tokens-file /run/secrets/jacobian-tokens.json \
  --public-base-url https://math-tools.example.org
```

Put a TLS-terminating reverse proxy in front of `127.0.0.1:8000`. The public
URL must route `/mcp` without stripping the path. Each authenticated subject is
mapped to a separate hashed directory below
`/var/lib/jacobian/tenants/`.

For a disposable local transport test only:

```sh
uv run jacobian-mcp \
  --transport streamable-http \
  --tool-profile capabilities \
  --allow-anonymous
```

Do not expose anonymous mode to a network.

## Container deployment

Build the repository image:

```sh
docker build -t jacobian:local .
```

Run it with a persistent state volume and read-only secret mount:

```sh
docker run --rm -p 127.0.0.1:8000:8000 \
  -v jacobian-state:/var/lib/jacobian \
  -v "$PWD/tokens.json:/run/secrets/jacobian-tokens.json:ro" \
  jacobian:local \
  --transport streamable-http \
  --tool-profile capabilities \
  --host 0.0.0.0 \
  --port 8000 \
  --state-dir /var/lib/jacobian \
  --auth-tokens-file /run/secrets/jacobian-tokens.json \
  --public-base-url https://math-tools.example.org
```

The initial static-token verifier is suitable for controlled deployments. A
hosted service should integrate its OAuth/OIDC verifier and map the validated
subject to the same tenant-routing interface.

## Operational boundaries

- Back up the state volume; artifacts and research episodes live there.
- Run one Jacobian process per state root until a lease model is implemented.
- Apply CPU, memory, filesystem, and network policy outside Jacobian.
- Do not interpret HTTP success, solver completion, or an MCP response as a
  verified mathematical result.
- Use the `full` profile only for trusted advanced clients that need the
  lower-level tool surface.
