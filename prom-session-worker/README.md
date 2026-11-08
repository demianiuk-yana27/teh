# Isolated Prom session Worker (deployment plan)

This is a **separate, machine-only reader** for the existing encrypted Prom session in Cloudflare D1. It does not change the Pages UI, existing upload/transfer endpoints, or the reviews/export workflows.

## Deployment (manual Cloudflare dashboard)
1. Create a Cloudflare Worker, e.g. `teh-prom-session-reader`, and deploy `prom-session-worker.js` as its code. Use its own `*.workers.dev` hostname; do not attach a route to the Pages site.
2. Bind **the same D1 database** used by Pages as `TASKS_DB`. Do not create an empty new database.
3. Configure encrypted secrets `PROM_SESSION_MACHINE_TOKEN` and `PROM_SESSION_ENCRYPTION_KEY` with **the exact existing Cloudflare Pages values**. Never paste them into GitHub, logs or chat. This is required to authenticate Render and decrypt existing data.
4. Test Worker `GET /prom-session` without Authorization: expect 401 (and no cookies). Confirm its request does not get BIC-blocked in Cloudflare HTTP logs.
5. In Render `teh-new`, change **only** `PROM_SESSION_VAULT_URL` to `https://<your-worker>.workers.dev/prom-session`. Keep `PROM_SESSION_MACHINE_TOKEN` unchanged. The existing Render code currently pins the Pages hostname; update that allowlist separately, only after the Worker URL is known and tested.
6. Run diagnostics and verify authenticated vault read and subsequent Prom access. If Worker returns 403/BIC too, stop; do not disable site-wide security. Roll back the Render URL if needed.

## Security
- Only GET /prom-session; other routes return 404.
- Bearer token required; no browser-role fallback and no CORS.
- Cookies returned only to authenticated machine clients, over HTTPS, with no-store.
- Existing AES-GCM ciphertext remains in D1; no plaintext secrets committed.
- Protect Worker hostname with appropriate Cloudflare access controls where supported, but ensure machine-to-machine calls remain functional.
