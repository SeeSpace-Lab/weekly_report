# Server deployment

The production-like review deployment lives entirely under
`/data1/chenwenjin`, following `SERVER_RULES.md`.

- WeRSS: `127.0.0.1:8001`
- Review site: `127.0.0.1:3000`
- Public HTTPS entry: `https://114-111-22-106.nip.io`
- `/feed/*` requires a bearer token.
- The review site requires HTTP Basic authentication.

Runtime secrets are stored outside the repository under
`/data1/chenwenjin/services/caddy` with mode `0600`.

The user-level systemd units keep WeRSS, the review site and Caddy running.
`weekly-report.timer` generates a new report every Monday at 09:00
Asia/Shanghai and restarts the review site after a successful build.

Before the public endpoint can obtain its TLS certificate, the cloud
security group must allow inbound TCP ports 80 and 443. Keep port 8001
closed to the public Internet; WeRSS is exposed only through Caddy's
authenticated `/feed/*` route.

The repository GitHub Action is manual-only during development. The
server timer updates the private review site first; publishing to GitHub
Pages is a separate, reviewer-approved step.

## Compliance audit

All project code, Conda environments, runtime data and logs are under
`/data1/chenwenjin`. Both project environments were cloned from
`tool-base`; no global Python or system package set was modified.

The only persistent entries outside `/data1/chenwenjin` are user-owned
systemd symlinks under `/home/chenwenjin/.config/systemd/user`. The
deployment also enabled linger for `chenwenjin` and assigned
`cap_net_bind_service` to the Caddy binary stored under the allocated
project directory. These operations provide user-service persistence and
low-port binding; they do not modify another user's files or global
dependencies.
