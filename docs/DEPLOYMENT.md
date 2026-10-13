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

For a first look without a real domain, set `DJANGO_SETTINGS_MODULE=config.settings.dev` in `.env`
instead of using the production settings.

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
  so a plain-HTTP probe works. The image has a Docker `HEALTHCHECK` using it.
- The worker log shows each failed email and YouTube sync; failures never reach users, so watch the logs.
- Unhandled errors return a generic JSON `500` and are logged with the full traceback.

## 6. Things to know

- **YouTube refresh tokens expire after 7 days** while the Google app is in Testing mode. Creators then get
  a "reconnect" notification and their last stats stay visible, marked outdated. Verifying the Google app
  removes the limit. A creator's stats refresh daily at 03:00 UTC.
- **Emails:** password reset codes are sent through the worker. If the provider is down the user still sees
  the same message and can request a new code later; check the worker log.
- **Demo data** (`seed_demo`) refuses to run in production because it creates accounts with a public password.
- **HSTS preload** is enabled in the production settings. Only serve the API over HTTPS on a domain you
  intend to keep on HTTPS.
- **Backups:** back up PostgreSQL. Redis only holds queued jobs and counters and can be rebuilt.

## 7. Checklist before going live

- [ ] `python manage.py check --deploy` reports no issues with the production environment
- [ ] `ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` list only the real host and frontend
- [ ] The proxy sets and overwrites `X-Forwarded-Proto` / `X-Forwarded-For`
- [ ] Migrations have been applied and exactly one `beat` is running
- [ ] A real password reset email reaches a Gmail and an Outlook inbox
- [ ] Google OAuth redirect URI matches `GOOGLE_REDIRECT_URI` and test users are added
