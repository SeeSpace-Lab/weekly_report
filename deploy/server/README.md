# Server deployment

The production-like review deployment lives entirely under
`/data1/chenwenjin`, following `SERVER_RULES.md`.

- WeRSS: `127.0.0.1:8001`
- Review site: `127.0.0.1:3000`
- Tunnel-ready authenticated entry: `127.0.0.1:8080`
- Public HTTPS entry: `https://114-111-22-106.nip.io`
- `/feed/*` requires a bearer token.
- The review site requires HTTP Basic authentication.

Runtime secrets are stored outside the repository under
`/data1/chenwenjin/services/caddy` with mode `0600`.
The weekly pipeline runtime file is
`/data1/chenwenjin/services/weekly-report/runtime.env`, also with mode `0600`.
It provides `WEEKLY_LLM_API_KEY`, `WEEKLY_LLM_MODEL`,
`WEEKLY_LLM_BASE_URL` and `WEEKLY_FETCH_FULLTEXT`.

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

`weekly-review-api.service` listens only on `127.0.0.1:8010`. Caddy exposes
its fixed status and approval endpoints behind the same HTTP Basic
authentication as the review site. Approval runs the evidence quality gate,
marks the issue approved, rebuilds the private site and pushes only
allowlisted generated report files with a repository-scoped GitHub deploy
key. It never triggers the Pages workflow.

Until the cloud security group opens ports 80 and 443, open the complete
authenticated review site (including the approval API) through an SSH tunnel:

```bash
ssh -p 10023 -L 3010:127.0.0.1:8080 chenwenjin@114.111.22.106
```

Then visit `http://127.0.0.1:3010`. Port 8080 is bound to server loopback and
is not directly exposed to the Internet.

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
