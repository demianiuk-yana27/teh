# Тех.Відділ — Windows Quick Requests

Native Windows application (Tkinter) that sends directly to **Google Apps Script → Google Sheets**. No Cloudflare, Render or new Google account is required.

## Setup (Google account that already has edit access to both sheets)

1. Open https://script.google.com/home/projects and choose **New project**.
2. Copy all code from [apps_script/Code.gs](apps_script/Code.gs) into the script editor, replacing the default content. Save.
3. In **Project Settings → Script properties**, add **QUICK_REQUESTS_KEY** with a random 48–64-character secret. The previously generated Cloudflare key may be reused, but keep it private.
4. Choose **Deploy → New deployment → Web app**. Set **Execute as: Me** and **Who has access: Anyone**. Authorize the requested Google Sheets access in your own Google account. Copy the URL ending in `/exec`.
5. Open the Windows application → **Налаштувати підключення до Google**, enter the deployment URL and the same key once. No Google login for managers.
6. Test a harmless request and check the exact row in the target Google Sheet before distributing the program.

**Security:** The web app is publicly reachable but rejects requests without the shared key. Anyone with the key can write to the two configured spreadsheets, so distribute privately, rotate on suspected leakage, and avoid granting this script any other permissions. A shared key does not provide per-device revocation or rate limiting. Apps Script executions are subject to Google's quotas. The key and URL are stored in `%APPDATA%\\TehQuickRequests\\settings.json` in plain text, readable by the Windows user. Do not commit or embed the key in the executable.

## Build the Windows executable

Open the GitHub Actions workflow **Build Windows Quick Requests** and download the artifact `TehQuickRequests-Windows`. Or run `build_windows.bat` on Windows with Python 3.11+.

## Notes

- The existing website and its Cloudflare/Render integrations are **not changed**.
- Google Apps Script `LockService` serializes simultaneous submissions.
- Request IDs are cached for up to 6 hours to prevent accidental retries of the same ID.
- The desktop program creates a new ID for each new submission; if a request times out, **check the sheet before submitting again**.
- For Tech, the last occupied B row determines the next write position.
- Changes to `Code.gs` require deploying a **new version** of the web app.
