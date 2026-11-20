# Тех.Відділ — Windows

Native Tkinter desktop client for https://teh-7rt.pages.dev/quick-requests/.

## Build on Windows
Install Python 3.11+ and run `build_windows.bat`. The executable is created at `desktop/dist/TehQuickRequests.exe`. The repository contains source code, **not a prebuilt .exe**.

## One-time admin setup
1. Generate a random secret of at least 32 characters (prefer 48+ cryptographically random characters).
2. In Cloudflare Pages project `teh-7rt`, add the secret environment variable `QUICK_REQUESTS_DESKTOP_KEY` for the production environment and redeploy.
3. Share the executable with approved users and distribute the key separately. Each user enters it once via **Налаштувати ключ програми**. There is no site-account login.
4. The key is stored in the current Windows user's `%APPDATA%\TehQuickRequests\settings.json`. Treat this file as sensitive. For stronger device security, migrate to Windows Credential Manager.
5. If a copy or key leaks, rotate the Cloudflare secret and reissue the key. The shared key is **not device-specific**, and anyone possessing it can submit requests. Apply Cloudflare WAF/rate limiting to `/quick-requests/` and monitor usage. Do not embed the key in the executable.

## Data
- `🐿️ Бурундуки`: 2 Відділ / Тех / Опт/дроп
- `📦 Зміни з ТТН`: order, TTN, error category and change type
- The backend adds Kyiv timestamps and performs read-after-write verification.
- The client never has Google Sheets credentials.

## Notes
The backend accepts a provisioned desktop key in `functions/quick-requests/index.js`; normal browser authentication is unchanged. The desktop application requires HTTPS connectivity to the Cloudflare site. The secret must be configured before desktop requests can succeed.
