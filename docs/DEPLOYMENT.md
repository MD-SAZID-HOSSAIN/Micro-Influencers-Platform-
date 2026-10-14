# Deployment guide

The backend is one Docker image that runs three ways: the **API** (gunicorn), a **Celery worker** and a
**Celery beat** scheduler. It needs PostgreSQL 16 and Redis 7. Nothing in the repository chooses a host;
this guide describes what any host must provide.

## 1. What must be in place

| Need | Why |
|---|---|
| PostgreSQL 16 with backups | The only durable store. Accepting proposals relies on its row locks. |
| Redis 7 | Celery's queue and the shared cache that rate limiting uses. |
| A TLS-terminating reverse proxy | The app redirects to HTTPS and trusts the proxy for the client IP (see 4). |
| An SMTP provider with SPF and DKIM on the sender domain | Password reset codes are email-only; unauthenticated mail lands in spam. |
| A Google OAuth app (Testing mode is fine) | Only needed to connect YouTube. See the README. |

## 2. Configuration

Set the variables in the README's table in the environment (or an `.env` file read by `docker compose`).
In production the settings **refuse to start** if any of these is unsafe: `SECRET_KEY` empty,
`ALLOWED_HOSTS` empty or `*`, `CORS_ALLOWED_ORIGINS` empty, `*`, or not `https://`, and
`OAUTH_ENCRYPTION_KEY` empty.

Generate the secrets once and keep them safe (losing `OAUTH_ENCRYPTION_KEY` means every creator has to
reconnect YouTube):

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"                                  # SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"      # OAUTH_ENCRYPTION_KEY
```

## 3. Build and run

```bash
docker compose build
docker compose run --rm web python manage.py migrate       # apply database migrations
docker compose up -d                                       # db, redis, web, worker, beat
```

Create the first admin account (there is no sign-up for admins):

```bash
docker compose run --rm web python manage.py create_admin --email you@example.com --username you
```

The containers always run the **production** settings (`docker-compose.yml` forces
`DJANGO_SETTINGS_MODULE=config.settings.prod`, so a `.env` copied from `.env.example` cannot switch them
to development). For a first look over plain HTTP without a real domain, put these in `.env`:
`ALLOWED_HOSTS=localhost`, `CORS_ALLOWED_ORIGINS=https://localhost:3000`, `SECURE_SSL_REDIRECT=false`,
a long `SECRET_KEY` and a real `OAUTH_ENCRYPTION_KEY`.

Anything that runs the app outside these containers (`gunicorn`, `celery`, `manage.py` on a server) also
starts in production mode by default, and refuses to start if those values are missing.

Roll out a new version by rebuilding, running `migrate` first, then restarting `web`, `worker` and `beat`.

**Run exactly one `beat`.** It is the scheduler; two instances would queue every daily YouTube sync and
every campaign auto-close twice. You can run as many `worker` and `web` replicas as you need.

## 4. The reverse proxy

The production settings assume exactly one proxy in front of the app (`NUM_PROXIES=1`). The proxy must:

- terminate TLS and forward to port 8000;
- set `X-Forwarded-Proto: https` and `X-Forwarded-For` itself, **discarding any value the client sent**.
  If it passes client values through, a client can fake its IP and dodge the login, registration and
  password-reset rate limits;
- not be bypassable: do not expose port 8000 directly to the internet.

If your setup has a different number of proxies, set `NUM_PROXIES` to match.

## 5. Health and monitoring

- `GET /api/v1/health/` returns `{"status": "ok", "database": "ok"}` and is exempt from the HTTPS redirect,
  so a plain-HTTP probe works. In `docker-compose.yml` only the `web` service has this probe. The image itself
has no `HEALTHCHECK` on purpose: the Celery worker and beat use the same image but listen on no port,
so an image-level web probe would mark them unhealthy forever. On another platform, attach the HTTP
health check to the web container only.
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
- **Backups:** back up PostgreSQL. Redis only holds queued jobs and counters and can be rebuilt.

## 7. Checklist before going live

- [ ] `python manage.py check --deploy` reports no issues with the production environment
- [ ] `ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` list only the real host and frontend
- [ ] The proxy sets and overwrites `X-Forwarded-Proto` / `X-Forwarded-For`
- [ ] Migrations have been applied and exactly one `beat` is running
- [ ] A real password reset email reaches a Gmail and an Outlook inbox
- [ ] Google OAuth redirect URI matches `GOOGLE_REDIRECT_URI` and test users are added
