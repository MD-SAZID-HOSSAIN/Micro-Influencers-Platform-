# Deployment guide

The backend runs as three processes from the same code: the **API** (gunicorn), a **Celery worker** and a
**Celery beat** scheduler. It needs PostgreSQL 16 and Redis 7, installed on the server (the repository ships no
container files). Nothing in the repository chooses a host; this guide describes what any host must provide.

## Free hosting: Vercel + Render + Neon

The website runs on **Vercel**, the API on **Render** and the database on **Neon**, all on free plans. The files for
this are `frontend/vercel.json` and `render.yaml`. It is good for a demo or portfolio. Read "What the free plans cost
you" at the end of this section before real people use it.

### Order of setup

The three services need each other's addresses, so deploy in this order and fill the gaps afterwards.

**1. Neon (database)**
1. Create a project. Choose the region closest to your users (AWS Singapore for South Asia) and use the same region
   on Render.
2. Open **Connect**, turn **Connection pooling off**, and copy the connection string. It must end in
   `?sslmode=require`. Use this *direct* string: the pooled one can interfere with the row locks that stop a brand
   accepting more creators than it asked for.

**2. Render (API)**
1. Push the repository to GitHub. In Render choose **New, Blueprint**, pick the repository and apply `render.yaml`.
   It creates the API (`collabnest-api`) and a Redis-compatible store (`collabnest-redis`).
2. Render asks for the variables marked `sync: false`. Fill in what you know now and put temporary values for the
   rest (you will fix them in step 4):

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | the Neon string from step 1 |
   | `ALLOWED_HOSTS` | the API host, e.g. `collabnest-api.onrender.com` (no `https://`). The host is shown on the service page; if the name was taken it gets a suffix. |
   | `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS` | temporary `https://example.vercel.app` (must start with `https://`) |
   | `OAUTH_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
   | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | from the Google Cloud console |
   | `GOOGLE_REDIRECT_URI` | `https://<api host>/api/v1/social/youtube/callback/` |
   | `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | Brevo SMTP login, SMTP key and a verified sender |
   | `YOUTUBE_API_KEY` | optional |

3. Wait for the first deploy. The build installs the packages and runs the database migrations. Then open
   `https://<api host>/api/v1/health/`. It should answer `{"status": "ok", "database": "ok"}`.

**3. Vercel (website)**
1. **Add New, Project**, pick the same repository and set **Root Directory** to `frontend`. Vercel reads
   `frontend/vercel.json` (Vite build, `dist` folder, and the rewrite that makes page refreshes work).
2. Add the environment variable `VITE_API_URL` = `https://<api host>/api/v1`, then deploy.
3. Copy the website address Vercel gives you (for example `https://collabnest.vercel.app`).

**4. Back to Render and Google**
1. Set `FRONTEND_URL` and `CORS_ALLOWED_ORIGINS` to the Vercel address (no trailing slash). Saving redeploys the API.
2. In the Google Cloud console add `https://<api host>/api/v1/social/youtube/callback/` as an authorized redirect URI
   and add your testers as test users.

**5. Create the first admin (once, from your own computer)**

Render's free plan has no shell, so run the command here against the Neon database. In PowerShell, in the project
folder with the virtual environment active:

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.dev"
$env:DATABASE_URL = "<the Neon string>"
python manage.py create_admin --email you@example.com --username you
```

The same two lines before `python manage.py seed_demo` fill the site with demo accounts, if you want them (they
share a public password, so do not leave them on a real site). Close the window afterwards so the string is not kept.

**6. Try it**: sign up, confirm the email code, log in as the admin at `/admin/login`.

### What the free plans cost you

- **Uploads are off** (`UPLOADS_ENABLED=false`). Render's disk is wiped on every deploy, so photos and videos cannot be
  kept. Campaign photos and videos cannot be added at all; profile pictures and logos can be set from a pasted image
  link. Real uploads need external storage (S3, Supabase Storage, Cloudflare R2) and a code change.
- **No background worker.** `CELERY_TASK_ALWAYS_EAGER=true` makes emails and the first YouTube sync run inside the
  request (an email adds about a second). The scheduled jobs do **not** run: the daily YouTube refresh (03:00 UTC),
  the daily video statistics refresh, and the five-minute campaign auto-close. Expired campaigns still stop taking
  applications and leave the creators' list, but their status stays "Published" until a brand closes them. To run the
  daily YouTube refresh you need a paid Render worker plus scheduler (the commands are in section 3 below), or an
  outside scheduler.
- **The free API sleeps when idle.** The first request after a quiet period can take 30 to 60 seconds (logins and the
  Google redirect feel it). An outside pinger on `/api/v1/health/` every few minutes keeps it awake.
- **Neon sleeps too** and wakes in a few seconds. Brevo's free plan sends about 300 emails a day.
- **The free Redis store** only holds counters and sign-in tokens; losing it is harmless.
- **Previews:** `CORS_ALLOWED_ORIGINS` lists exact addresses, so Vercel preview deployments cannot call the API unless
  you add their address.

When real users arrive, upgrade in this order: a paid Render worker and scheduler (set `CELERY_TASK_ALWAYS_EAGER` back
to `false` and add the two `celery` services, section 3), then external storage for uploads (`UPLOADS_ENABLED=true`),
then paid plans so nothing sleeps.

---

## 1. What must be in place

| Need | Why |
|---|---|
| PostgreSQL 16 with backups, listening only on the server itself (or a private network), with a strong password | The only durable store. Accepting proposals relies on its row locks. |
| Redis 7, with a password, listening only on the server itself (or a private network) | Celery's queue and the shared cache that rate limiting uses. Never expose it to the internet. |
| A TLS-terminating reverse proxy | The app redirects to HTTPS and trusts the proxy for the client IP (see 4). |
| An SMTP provider with SPF and DKIM on the sender domain | Password reset codes are email-only; unauthenticated mail lands in spam. |
| A Google OAuth app (Testing mode is fine) | Only needed to connect YouTube. See the README. |

## 2. Configuration

Set the variables in the README's table in the process environment (or an `.env` file in the project folder).
In production the settings **refuse to start** if any of these is unsafe: `SECRET_KEY` empty,
`ALLOWED_HOSTS` empty or `*`, `CORS_ALLOWED_ORIGINS` empty, `*`, or not `https://`, and
`OAUTH_ENCRYPTION_KEY` empty.

Generate the secrets once and keep them safe (losing `OAUTH_ENCRYPTION_KEY` means every creator has to
reconnect YouTube):

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"                                  # SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"      # OAUTH_ENCRYPTION_KEY
```

## 3. Install and run

On the server, in the project folder (Python 3.12 or newer):

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements/base.txt
export DJANGO_SETTINGS_MODULE=config.settings.prod   # also the default when nothing is set
python manage.py migrate                              # apply database migrations
```

Run these three as services (systemd, supervisor or your host's process manager), restarting them if they stop:

```bash
gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3 --access-logfile -   # the API
celery -A config worker -l info                                                          # background jobs
celery -A config beat -l info                                                            # scheduler
```

Create the first admin account (there is no sign-up for admins):

```bash
python manage.py create_admin --email you@example.com --username you
```

Run all three as an unprivileged user, never as root. `gunicorn`, `celery` and `manage.py` start in
**production** mode by default, and refuse to start if the values listed in section 2 are missing. For a first
look over plain HTTP without a real domain, put these in `.env`: `ALLOWED_HOSTS=localhost`,
`CORS_ALLOWED_ORIGINS=https://localhost:3000`, `SECURE_SSL_REDIRECT=false`, a long `SECRET_KEY` and a real
`OAUTH_ENCRYPTION_KEY`.

Roll out a new version by pulling the code, running `pip install` and `migrate`, then restarting the API,
the worker and the scheduler.

**Run exactly one `beat`.** It is the scheduler; two instances would queue every daily YouTube sync and
every campaign auto-close twice. You can run as many `worker` and API processes as you need.

## 4. The reverse proxy

The production settings assume exactly one proxy in front of the app (`NUM_PROXIES=1`). The proxy must:

- terminate TLS and forward to port 8000;
- set `X-Forwarded-Proto: https` and `X-Forwarded-For` itself, **discarding any value the client sent**.
  If it passes client values through, a client can fake its IP and dodge the login, registration and
  password-reset rate limits;
- not be bypassable: bind gunicorn to `127.0.0.1` (as above) so port 8000 is not reachable from the internet.

If your setup has a different number of proxies, set `NUM_PROXIES` to match.

## 5. Health and monitoring

- `GET /api/v1/health/` returns `{"status": "ok", "database": "ok"}` and is exempt from the HTTPS redirect,
  so a plain-HTTP probe works. Point the probe at the API process only: the Celery worker and beat listen on no
port, so they have nothing to probe.
- The worker log shows each failed email and YouTube sync; failures never reach users, so watch the logs.
- Unhandled errors return a generic JSON `500` and are logged with the full traceback.

## 6. Things to know

- **YouTube refresh tokens expire after 7 days** while the Google app is in Testing mode. Creators then get
  a "reconnect" notification and their last stats stay visible, marked outdated. Verifying the Google app
  removes the limit. A creator's stats refresh daily at 03:00 UTC.
- **Emails:** password reset codes are sent through the worker. If the provider is down the user still sees
  the same message and can request a new code later; check the worker log.
- **Demo data** (`seed_demo`) refuses to run in production because it creates accounts with a public password.
- **HSTS:** production sends a one-year `Strict-Transport-Security` header (`SECURE_HSTS_SECONDS`; try `300`
  for a first rollout). Subdomain locking (`SECURE_HSTS_INCLUDE_SUBDOMAINS`) and browser preload
  (`SECURE_HSTS_PRELOAD`, which needs the subdomain option) are **off** by default because they are very hard
  to undo. Turn them on only for a domain that will always use HTTPS.
- **If Redis goes down:** the API keeps working. Login, sign-up, password reset and email verification are
  still served, but **rate limits are not enforced** until Redis is back (a warning
  "Rate limiting is unavailable" is logged for each request). The YouTube connect step answers `503
  temporarily_unavailable` (the user can try again). Work that could not be queued is logged ("Could not
  queue background task") and the daily YouTube sync picks it up. Cache calls give up after 2 seconds.
- **Daily YouTube sync** is spread over `YOUTUBE_SYNC_SPREAD_SECONDS` (default 1800) after 03:00 UTC instead of
  starting every creator at the same second.
- **Uploaded photos and videos** (campaign briefs) are written to `MEDIA_ROOT` (the `media/` folder next to
  `manage.py`) and linked as `/media/...`. Django only serves that folder in development (`DEBUG`), so in
  production either serve it from the web server and keep the folder on persistent storage, or move it to
  object storage such as S3. Without one of these, the links do not open. Let the proxy accept request bodies of at least 55 MB
  (nginx: `client_max_body_size 55m`), since a video may be up to 50 MB.
- **Backups:** back up PostgreSQL, and the media folder if you keep uploads on local disk. Redis only holds
  queued jobs and counters and can be rebuilt.

## 7. Checklist before going live

- [ ] `python manage.py check --deploy` reports no issues with the production environment
- [ ] `ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` list only the real host and frontend
- [ ] The proxy sets and overwrites `X-Forwarded-Proto` / `X-Forwarded-For`
- [ ] Migrations have been applied and exactly one `beat` is running
- [ ] A real password reset email reaches a Gmail and an Outlook inbox
- [ ] Google OAuth redirect URI matches `GOOGLE_REDIRECT_URI` and test users are added
