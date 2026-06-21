# Deployment Context

## Existing Topology

- `dmit` is the public entry machine and forwards traffic through WireGuard /
  nginx stream.
- `hostdzire` is the application deployment machine and runs the Docker Compose
  stack, local nginx, MySQL, Redis, API, and worker.
- Normal code updates only touch hostdzire.

## Existing Runtime Contract

- Repository path on hostdzire: `/root/md2word`
- Compose file: `/root/md2word/docker/prod/docker-compose.yml`
- Runtime environment: `/root/md2word/.env`
- Public URL: `https://md2word.962850.xyz`
- Local API origin on hostdzire:
  `http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}`

## Release Flow Chosen For This Task

Use GitHub as the source of truth:

1. Push local `main` to `origin/main`.
2. SSH to hostdzire using private VPS information stored outside the repo.
3. If `/root/md2word` exists, `git fetch` and fast-forward to `origin/main`.
   Otherwise clone `git@github.com:ccisnoxx/md2word.git` there.
4. Preserve `.env`, internal users JSON, volumes, MySQL data, Redis data, and
   nginx configuration.
5. Rebuild and restart the Compose stack.
6. Run loopback and public health checks.

## Documentation Constraint

The final deployment documentation must never include raw VPS credentials,
tokens, passwords, IP addresses from the private file, or secret environment
values.
