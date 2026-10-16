# Micro-Influencers' Platform: Backend

Django REST API for a two-sided marketplace that connects micro-influencers (creators) with brands.
Creators build profiles with audience stats and rates and apply to campaigns; brands discover creators,
post campaigns and manage the proposals they receive.

- Product spec: [`PRD_Micro-Influencers_Platform.md`](PRD_Micro-Influencers_Platform.md)
- Build plan: [`plan.md`](plan.md)
- API reference: Swagger UI at **`/api/docs/`** while the server runs, or import
  [`docs/openapi.yml`](docs/openapi.yml) into Postman / Insomnia.
- Frontend integration guide: [`docs/FRONTEND_GUIDE.md`](docs/FRONTEND_GUIDE.md)
- Deployment: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)
- Design decisions and known gaps: [`docs/DECISIONS.md`](docs/DECISIONS.md)

## Requirements

- Python 3.12 or newer
- PostgreSQL 16 and Redis 7 (Docker is the easiest way to get both)

The test suite needs a real PostgreSQL: the "accept never exceeds Creators Needed" guarantee relies on
row locks that SQLite does not provide.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements/dev.txt
cp .env.example .env                   # then edit the values you need
docker compose up -d db redis         # PostgreSQL + Redis
python manage.py migrate
python manage.py seed_demo             # optional demo data (see below)
python manage.py runserver
```

Check it works: `GET http://localhost:8000/api/v1/health/` returns `{"status": "ok", "database": "ok"}`,
and `http://localhost:8000/api/docs/` shows the API reference.

### Demo data

`python manage.py seed_demo` creates 200 creators, 20 brands, 100 campaigns and their proposals so the
frontend has something to show. It only runs when `DEBUG` is on, is safe to repeat (it tops up what is
missing) and produces the same data every time. Options: `--creators`, `--brands`, `--campaigns`.

Log in as `demo_creator_001` or `demo_brand_01` with password **`DemoPass123!`**.

## Tests

```bash
pytest                       # whole suite
pytest apps/proposals -v     # one app
```

Tests use `config.settings.test` (set in `pytest.ini`) and read `DATABASE_URL`: point it at any
PostgreSQL the user may create databases on. Email is captured in memory and background tasks run
immediately, so no Redis or SMTP server is needed.

## Background workers

Email, YouTube stat syncs and campaign auto-closing run in Celery.

```bash
celery -A config worker -l info --pool=solo   # --pool=solo is required on Windows
celery -A config beat -l info                 # the scheduler; run exactly ONE instance
```

Scheduled jobs: every creator's YouTube stats are refreshed daily at 03:00 UTC, and campaigns whose
application deadline has passed are closed every 5 minutes.

## Admin accounts

Admins cannot register through the API. Create one on the server:

```bash
python manage.py create_admin --email you@example.com --username you
```

The password is prompted for (twice) and is never accepted as an argument. Admins sign in at
`POST /api/v1/admin/auth/login/`; the public login rejects admin accounts, and ordinary accounts
cannot use the admin login. Every admin action (suspend, reactivate, delete, close a campaign,
remove a review) needs a written reason and is recorded in `GET /api/v1/admin/actions/`.

## Connecting YouTube (Google OAuth)

Only YouTube is connected through OAuth; Instagram, TikTok and Facebook use manual entry and are labelled
Unverified (see the PRD for why).

1. In the [Google Cloud console](https://console.cloud.google.com/) create a project and enable the
   **YouTube Data API v3**.
2. Configure the **OAuth consent screen** in **Testing** mode and add your test users' Google accounts.
   The only scope used is `https://www.googleapis.com/auth/youtube.readonly`.
3. Create an **OAuth client ID** of type *Web application* and add the redirect URI
   `<backend-url>/api/v1/social/youtube/callback/`.
4. Put the client ID, secret and redirect URI in `.env` (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
   `GOOGLE_REDIRECT_URI`), and generate `OAUTH_ENCRYPTION_KEY` as shown in `.env.example`.

**How the connection finishes (for the frontend).** It takes three steps so that only the person who
started it can finish it:

1. `GET /api/v1/social/youtube/connect/` (logged in) returns the Google URL; send the browser there.
2. After consent Google redirects the browser to the API's `/callback/`, which saves nothing and
   redirects on to `FRONTEND_URL/settings/connections?youtube=confirm&code=...&state=...`
   (or `?youtube=error&reason=access_denied|invalid_state`).
3. The frontend, logged in, sends both values unchanged to `POST /api/v1/social/youtube/complete/`
   with `{"state", "code"}`. It answers with the connection status, or a 400 whose `code` is
   `invalid_state`, `exchange_failed` or `no_refresh_token`. A `state` that was issued to a different
   creator is refused with `invalid_state`.

**While the app is in Testing mode, Google expires refresh tokens after 7 days**, so creators may need to
reconnect about once a week. The platform handles this: the creator gets a "reconnect" notification and
their last known stats stay visible, marked as outdated. Publishing the app (Google verification) removes
the limit.

## Configuration

All configuration comes from environment variables; nothing secret is stored in the repository. Copy
`.env.example` to `.env` for local development.

| Variable | Purpose |
|---|---|
| `DJANGO_SETTINGS_MODULE` | Which settings to run: `config.settings.dev` locally; leave unset (or `config.settings.prod`) on a server. |
| `SECRET_KEY` | Signs tokens and hashes reset codes. Long and random in production. |
| `ALLOWED_HOSTS` | Comma-separated host names the API answers to. |
| `DATABASE_URL` | PostgreSQL connection URL. |
| `REDIS_URL` | Redis for Celery and the shared cache (rate limiting). |
| `FRONTEND_URL` | Where the OAuth callback redirects, and the base of links in emails. |
| `CORS_ALLOWED_ORIGINS` | Comma-separated frontend origins allowed to call the API (https in production). |
| `NUM_PROXIES` | Reverse proxies in front of the app, so rate limiting sees the real client IP. `0` in development, `1` in production by default. |
| `SECURE_SSL_REDIRECT` | Production only: redirect HTTP to HTTPS. Set `false` only for a plain-HTTP smoke test. |
| `SECURE_HSTS_SECONDS` | Production only: how long browsers must keep using HTTPS for this site (default one year; try `300` for a first rollout). |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | Production only, default `false`: also lock every subdomain to HTTPS. Hard to undo. |
| `SECURE_HSTS_PRELOAD` | Production only, default `false`: ask to be baked into browsers' HTTPS-only lists. Needs the option above; very hard to undo. |
| `OAUTH_ENCRYPTION_KEY` | Fernet key that encrypts stored YouTube tokens. Required in production. |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID. |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret. |
| `GOOGLE_REDIRECT_URI` | The callback URL registered with Google. |
| `YOUTUBE_API_KEY` | Optional server key for public video statistics (brand analytics). Without it, content performance shows `not_available`. |
| `EMAIL_BACKEND` | Django email backend; console in development, SMTP in production. |
| `EMAIL_HOST` | SMTP host. |
| `EMAIL_PORT` | SMTP port. |
| `EMAIL_HOST_USER` | SMTP user. |
| `EMAIL_HOST_PASSWORD` | SMTP password. |
| `EMAIL_USE_TLS` | Use TLS for SMTP. |
| `DEFAULT_FROM_EMAIL` | The sender address (set up SPF/DKIM for its domain). |
| `MEDIA_URL` | Base URL for uploaded user media (avatars, logos). Default `/media/`. |
| `MEDIA_ROOT` | Filesystem path where uploaded media files are stored. Default `<BASE_DIR>/media`. |

Settings modules: `config.settings.dev` (local development), `config.settings.test` (pytest) and
`config.settings.prod` (deployment; refuses to start with an unsafe configuration).

**Production is the default.** `manage.py`, wsgi and Celery start in production mode unless
`DJANGO_SETTINGS_MODULE` says otherwise, so a server that forgets the variable fails to start instead
of running in debug mode. For local work, the `.env` you copy from `.env.example` already contains
`DJANGO_SETTINGS_MODULE=config.settings.dev`.

## How the API behaves

- **Auth:** `POST /api/v1/auth/login/`, then send `Authorization: Bearer <token>`. Tokens last 24 hours.
  Logging out or resetting a password signs the user out everywhere.
- **Errors:** always `{"error": {"code", "message", "details"}}`. Branch on `code`.
- **Lists:** `count`, `next`, `previous`, `results`; `?page=` and `?page_size=` (max 50).
- **Roles:** creators and brands see different endpoints; the wrong role gets 403 and another account's
  data is 404.

## Project layout

```
config/            settings (base / dev / test / prod), URLs, Celery
apps/core/         shared plumbing: error format, pagination, permissions, email, demo data
apps/accounts/     users, registration, login, password reset
apps/profiles/     creator and brand profiles, portfolio, creator directory
apps/social/       platform stats, YouTube OAuth and sync
apps/campaigns/    campaigns and their lifecycle, creator-facing discovery
apps/proposals/    applying, withdrawing, shortlist / accept / reject
apps/notifications/ in-app notifications
apps/dashboards/   the creator and brand home screens
docs/              OpenAPI file and the deployment guide
```

Business rules live in each app's `services.py`; views stay thin.

## Working on this repository

Work on a feature branch and open a pull request into `main`. When you change an endpoint, regenerate the
API file (a test fails if it is stale):

```bash
python manage.py spectacular --file docs/openapi.yml
```
