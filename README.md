# Micro-Influencers' Platform: Backend

Django REST API for a two-sided marketplace that connects micro-influencers (creators) with brands.
Creators build profiles with audience stats and rates and apply to campaigns; brands discover creators,
post campaigns and manage the proposals they receive.

- Product spec: [`PRD_Micro-Influencers_Platform.md`](PRD_Micro-Influencers_Platform.md)
- Build plan: [`plan.md`](plan.md)
- API reference: Swagger UI at **`/api/docs/`** while the server runs, or import
  [`docs/openapi.yml`](docs/openapi.yml) into Postman / Insomnia.
- Frontend app (React): [`frontend/`](frontend/README.md). Run `npm install && npm run dev` there.
- Frontend integration guide: [`docs/FRONTEND_GUIDE.md`](docs/FRONTEND_GUIDE.md)
- Deployment: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)
- Design decisions and known gaps: [`docs/DECISIONS.md`](docs/DECISIONS.md)

## Requirements

- Python 3.12 or newer
- PostgreSQL 16 and Redis 7 (Docker is the easiest way to get both)

The test suite needs a real PostgreSQL: the "accept never exceeds Creators Needed" guarantee relies on
row locks that SQLite does not provide.

## Run the project

CollabNest is two programs: the Django API (port 8000) and the React website in [`frontend/`](frontend/)
(port 5173). Run each in its own terminal. You also need Node 20 or newer for the website.

### First-time setup

**Terminal 1: backend** (repo root)

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements/dev.txt
cp .env.example .env                   # Windows: copy .env.example .env
docker compose up -d db redis          # PostgreSQL + Redis (start Docker Desktop first)
python manage.py migrate
python manage.py seed_demo             # optional demo data (see below)
python manage.py runserver
```

**Terminal 2: frontend**

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. In development the website calls `/api/v1` on its own address and Vite
forwards it to Django, so no CORS setup is needed.

### Every time after that

1. Start Docker Desktop.
2. Terminal 1, from the repo root: `source .venv/bin/activate` (Windows: `.venv\Scripts\activate`), then
   `docker compose up -d db redis`, then `python manage.py runserver`.
3. Terminal 2: `cd frontend`, then `npm run dev`.
4. Open http://localhost:5173. Stop either server with `Ctrl + C`.

### Check it works

- `GET http://localhost:8000/api/v1/health/` returns `{"status": "ok", "database": "ok"}`.
- `http://localhost:8000/api/docs/` shows the API reference.
- `http://localhost:8000/` itself shows "Not Found": port 8000 is the API only, the website is on 5173.

### Where emails and codes go

In development emails are printed in the **backend terminal** (`EMAIL_BACKEND` is the console backend), so
that is where to find email-verification and password-reset codes. To send real email, set the SMTP
variables in `.env` (see Configuration below).

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

Admins cannot register through the website or the API. Create one on the server, with the backend
environment active (`.venv` activated, database running):

```bash
python manage.py create_admin --email you@example.com --username admin
```

The password (8 characters or more) is prompted for twice and is never accepted as an argument.

**Local development admin** (used in this project's local setup):

| | |
|---|---|
| Username | `admin` |
| Password | `12345678` |

To create it, run `python manage.py create_admin --email you@example.com --username admin` (use any email
address) and type `12345678` when it asks for the password. These are throwaway local credentials: on any
shared or deployed server, use a strong password instead.

**Log in as admin**

1. Start both servers (see Run the project).
2. Open **http://localhost:5173/admin/login**.
3. Enter the username `admin` and the password.

The admin area has an overview, a user list (search, suspend, reactivate, delete) and an audit log. The
public login page rejects admin accounts, and ordinary accounts cannot use the admin login. Every admin
action (suspend, reactivate, delete, close a campaign, remove a review) needs a written reason and is
recorded in `GET /api/v1/admin/actions/`. Through the API, admins sign in at
`POST /api/v1/admin/auth/login/`.

## Photos and videos on campaigns

While a campaign is a **draft**, its brand can attach **up to 2 photos or 1 video** (never both):

| | Types | Largest |
|---|---|---|
| Photo | JPG, PNG, WebP | 5 MB |
| Video | MP4, WebM | 50 MB |

- In the website, add them on **Create a campaign** or **Edit campaign**; they upload when the draft is saved or
  published. Creators see them on the campaign page.
- API: `POST /api/v1/brand/campaigns/<id>/media/` (multipart field `file`) and
  `DELETE /api/v1/brand/campaigns/<id>/media/<media_id>/`. The campaign payload lists them under `media`.
- The server decides what a file is by reading its first bytes, not its name or `Content-Type`, and stores it
  under a random name. Published and closed campaigns are frozen, so their media cannot change.
- Files are saved in `media/` (ignored by git) and served by Django in development only. See
  `docs/DEPLOYMENT.md` for production storage.

## Profile pictures

Creators have a **profile photo** and brands a **logo** (JPG, PNG or WebP, up to 5 MB). Both are set on the
**Edit profile** page and saved as soon as the file is chosen. They show in the header, on profiles, in the
creator search, on campaign cards and on the campaign page.

- API: `PUT /api/v1/creators/me/photo/` and `PUT /api/v1/brands/me/logo/` (multipart field `file`), and
  `DELETE` on the same addresses. Each returns the updated profile. The picture is the profile's
  `photo_url` / `logo_url`, and `GET /api/v1/auth/me/` reports it as `avatar_url`.
- A new upload replaces the old one (the old file is deleted). Setting `photo_url` / `logo_url` to a link
  through `PATCH` also replaces an uploaded picture, so there is only ever one.
- Stored and served like campaign media (see above), as paths such as `/media/profiles/photos/...`.

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

**Disconnecting** deletes the stored tokens and also revokes the grant at Google, so the app disappears from the
creator's Google account permissions. The revoke is best effort: if Google cannot be reached the creator is
still disconnected and a warning is logged. Failed sign-ins and syncs are logged with Google's reason code
(look for "YouTube" in the backend log); tokens, codes and keys are never logged.

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
