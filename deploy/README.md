# Existing EC2 workbench operations

Use the existing instance, Nginx and dedicated research service. These files do not
create AWS resources, open security groups, upgrade the account plan or authorize
market-data redistribution. Verify the actual account budget before deployment.

## Update an existing installation

The service must already be healthy, enabled and protected by certificate-verified
HTTPS with Basic authentication. Keep Streamlit on `127.0.0.1:8513`, with base path
`quant` and `AI_TRADE_READ_ONLY=1`. Preserve any existing Java service and HTTP route.
The shared micro instance uses a 240 MiB memory limit and 20% CPU quota. Heavy
collection and backtests stay local; a cold page may take longer under this quota.

Copy `deploy.env.example` outside the repository, fill in existing paths and set
owner-only permissions (`chmod 600`). Keep the curl credential file outside Git,
also owned by the deploy user with mode 600. Do not put passwords on command lines.

```bash
git -C /opt/a-share-quant-workbench/repository fetch --no-tags origin main
git -C /opt/a-share-quant-workbench/repository rev-parse origin/main
# Use the reviewed script and the explicit 40-character main SHA printed above.
bash deploy/update-workbench.sh MAIN_SHA /home/ubuntu/.config/a-share-quant-workbench/deploy.env
```

The updater validates the pinned SHA against fetched main, briefly stops only the
managed workbench to free memory, installs pinned dependencies, runs targeted
offline checks, rejects schema changes and makes an online SQLite backup including
committed WAL pages. It switches the code symlink and verifies the running release,
local health, authenticated HTTPS health and unchanged data contents. A failure
restarts the previous release and exits nonzero. It never restores/overwrites the
database automatically. Failed releases and older versions remain for inspection.

Use an existing dedicated persistent directory outside repositories and temporary
directories, such as `/var/lib/a-share-quant-workbench`. Never adopt `demo.sqlite3`
as deployment storage. Initializing an empty research store is a separate explicit
operator step; the updater cannot initialize or migrate one. Backups use unique
private filenames under `DATA_DIR/backups`. Check free space; no automatic pruning.

If `TLS_RESOLVE` is used, HTTPS is checked against local Nginx with its real public
certificate. This does **not** verify AWS ingress or phone connectivity. A public
TCP timeout, a TLS error, an HTTP error and an application error are separate states.
Never disable TLS verification to make a health check pass.

## IP certificate and access checks

The existing setup uses Certbot 5.8 and Let's Encrypt's `shortlived` IP certificate
profile. Public certificates last approximately six days, so automatic renewal is
required. The independent `quant-cert-renew.timer` checks twice daily; its service
runs `certbot renew --cert-name quant-ip --quiet`. A successful deploy hook tests and
reloads Nginx. HTTP-01 uses only `/.well-known/acme-challenge/` under a dedicated
public webroot; the original HTTP application route stays intact. See the
[CA instructions](https://letsencrypt.org/2026/03/11/shorter-certs-certbot).

```bash
sudo nginx -t
systemctl status a-share-quant-workbench.service quant-cert-renew.timer
sudo openssl x509 -in /etc/letsencrypt/live/quant-ip/fullchain.pem -noout -dates -ext subjectAltName
sudo journalctl -u quant-cert-renew.service --no-pager -n 10
sudo journalctl --namespace=quant -u a-share-quant-workbench.service --no-pager -n 20
```

Inspect the certificate actually served over TLS as well as the file. A successful
renewal check before the certificate is due is not proof of a completed renewal.
Verify unauthenticated and wrong-credential requests return 401 for the page,
static resources and Streamlit paths; authenticated health must return `ok`.
Then test the protected public HTTPS URL from the phone's network. Keep 8513 closed
to the Internet. Do not report phone acceptance from a local SSH tunnel or viewport
test. Nginx logs follow its existing daily rotation; the workbench journal namespace
is limited to 20 MiB and 14 days without changing Java/system logs.

AWS billing permissions and security-group access are independent of SSH access.
Without them, record the missing checks and request only the relevant console
action; do not provision substitutes or enable paid APIs/automatic deployment.
