# CollabNest: Micro-Influencers' Platform

A two-sided marketplace that connects **micro-influencers (creators)** with **brands**. Creators build a
profile with audience stats and rates and apply to campaigns. Brands find creators, publish campaigns and
manage the proposals they receive.

The repository holds both halves of the project:

| Part | Where | Stack | Port |
|---|---|---|---|
| REST API | repository root (`apps/`, `config/`) | Django, Django REST Framework, PostgreSQL, Redis, Celery | 8000 |
| Website | [`frontend/`](frontend/README.md) | React, TypeScript, Vite, Tailwind | 5173 |

Useful documents:

- Product spec: [`PRD_Micro-Influencers_Platform.md`](PRD_Micro-Influencers_Platform.md)
- API reference: Swagger UI at **`/api/docs/`** while the server runs, or import
  [`docs/openapi.yml`](docs/openapi.yml) into Postman or Insomnia
- Frontend integration guide: [`docs/FRONTEND_GUIDE.md`](docs/FRONTEND_GUIDE.md)
- Design decisions and known gaps: [`docs/DECISIONS.md`](docs/DECISIONS.md)
- Deployment: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)
- Build plan and report: [`plan.md`](plan.md), [`docs/BUILD_REPORT.md`](docs/BUILD_REPORT.md)

## Who can do what

| | Verified how | Can do only after verification |
|---|---|---|
| **Brand** | **Email**: a 6-digit code emailed after sign-up | Publish a campaign, accept a proposal |
| **Creator** | **YouTube**: connect a channel with Google sign-in (Verified stats) | Apply to a campaign |

- Unverified accounts can still log in, browse, edit their profile and (brands) save drafts, shortlist and reject.
- Only **brands** verify their email. For a creator, the verify and resend endpoints answer 403
  `email_verification_brands_only` and no code is sent at sign-up. A creator's email is used to reset a
  forgotten password, nothing else (so creators receive no notification emails; they see updates in the app).
- **Forgot password** works for every account, verified or not.
- The errors are 403 `brand_email_unverified` and 403 `creator_youtube_required`.
- This is stricter than the PRD. See "Verification gates" in [`docs/DECISIONS.md`](docs/DECISIONS.md).

## Requirements

- Python 3.12 or newer
- Node 20 or newer (for the website)
- PostgreSQL 16 and Redis 7. Docker is the easiest way to get both; native installs also work (see below)

The test suite needs a real PostgreSQL, because the "accepted never exceeds Creators Needed" guarantee relies on
row locks that SQLite does not have.

## Run the project

Run the API and the website in two terminals.

### First-time setup

**Terminal 1: backend** (repository root)

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

1. Start Docker Desktop (if you use it).
2. Terminal 1, from the repository root: activate the virtual environment, run `docker compose up -d db redis`,
   then `python manage.py runserver`.
3. Terminal 2: `cd frontend`, then `npm run dev`.
4. Open http://localhost:5173. Stop either server with `Ctrl + C`.

### Without Docker

- **PostgreSQL:** install version 16, create a database, and set `DATABASE_URL` in `.env`. The default in
  `.env.example` is `postgres://postgres:postgres@localhost:5432/microinfluencers`.
- **Redis:** install Redis 7 (Linux and macOS packages, WSL on Windows, or a Redis-compatible server such as
  Memurai) and keep `REDIS_URL` pointing at it.
- **No Redis at all:** everything works except two things. Rate limiting is skipped (the API logs a warning and
  lets the request through), and **connecting YouTube answers 503**, because its one-time sign-in token is kept in
  the shared cache. To run without it, create an untracked settings file `config/settings/local.py`:

  ```python
  from .dev import *  # noqa: F401,F403

  CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
  ```

  and set `DJANGO_SETTINGS_MODULE=config.settings.local` in `.env`. Do not commit that file, and use it only
  with a single `runserver` process.

### Check it works

- `GET http://localhost:8000/api/v1/health/` returns `{"status": "ok", "database": "ok"}`.
- `http://localhost:8000/api/docs/` shows the API reference.
- `http://localhost:8000/` itself shows "Not Found": port 8000 is the API only, the website is on 5173.

## Demo data

`python manage.py seed_demo` creates 200 creators, 20 brands, 100 campaigns and their proposals, so the website has
something to show. It only runs when `DEBUG` is on, is safe to repeat (it tops up what is missing and repairs the
verification flags), and gives the same data every time. Options: `--creators`, `--brands`, `--campaigns`.

Log in as `demo_creator_001` or `demo_brand_01` with password **`DemoPass123!`**.

- Every demo brand has a verified email.
- Every demo creator has a verified YouTube channel, except each fifth one (`demo_creator_005`, `010`, ...). Use
  those to see the "connect YouTube to apply" state.
- Demo accounts use fake `@demo.test` addresses. Do not point a real email provider at them (see "Email").

## Email

Reset codes, brand verification codes and notification emails all go through Django's mail system and are sent
in a background task that retries with growing delays. A failed send never breaks a request.

- **Development (default):** `EMAIL_BACKEND` is the console backend, so every email is **printed in the backend
  terminal**. That is where to find verification and password-reset codes. It works for any address.
- **Real email:** set the SMTP variables in `.env` and use `django.core.mail.backends.smtp.EmailBackend`.

  | Provider | Host | Port | Username | Password |
  |---|---|---|---|---|
  | Brevo | `smtp-relay.brevo.com` | 587 | the **SMTP login** on Brevo's *SMTP & API* page (looks like `a1b2c3001@smtp-brevo.com`, not your account email) | an SMTP key (`xsmtpsib-...`) |
  | Resend | `smtp.resend.com` | 587 | `resend` | an API key (`re_...`) |

  Set `EMAIL_USE_TLS=True` and make `DEFAULT_FROM_EMAIL` an address the provider has verified. Without a verified
  domain, Resend delivers only to the address you signed up with. Never commit keys.
- In development, background jobs run inside the request (`CELERY_TASK_ALWAYS_EAGER`), so a failing mail server can
  make a request slow while it retries.

## Tests

```bash
pytest                       # whole suite
pytest apps/proposals -v     # one app
cd frontend && npx tsc --noEmit    # type-check the website
```

Tests use `config.settings.test` (set in `pytest.ini`) and read `DATABASE_URL`: point it at any PostgreSQL where the
user may create databases. Email is captured in memory and background tasks run immediately, so the tests need
no Redis and no mail server. `tests_e2e/test_full_lifecycle.py` is a separate script that needs a running server.

## Background workers

Email, YouTube syncs and campaign auto-closing run in Celery. In development they run inside the request, so you
do not need a worker. For production (or with `CELERY_TASK_ALWAYS_EAGER=False`):

```bash
celery -A config worker -l info --pool=solo   # --pool=solo is required on Windows
celery -A config beat -l info                 # the scheduler; run exactly ONE instance
```

Scheduled jobs (UTC): every creator's YouTube stats refresh at 03:00, published-video statistics refresh at 04:00,
and campaigns whose application deadline has passed are closed every 5 minutes.

## Admin accounts

Admins cannot register through the website or the API. Create one on the server, with the backend environment
active and the database running:

```bash
python manage.py create_admin --email you@example.com --username admin
```

The password (8 characters or more) is prompted for twice and is never accepted as an argument.

**Local development admin** used in this project's local setup: username `admin`, password `12345678`. These are
throwaway credentials; on any shared or deployed server use a strong password instead.

Admins sign in at **http://localhost:5173/admin/login** (through the API: `POST /api/v1/admin/auth/login/`). The
admin area has an overview, a user list (search, suspend, reactivate, delete) and an audit log. The public login
page rejects admin accounts, and ordinary accounts cannot use the admin login. Every admin action needs a written
reason and is recorded in `GET /api/v1/admin/actions/`.

## Photos and videos

- **Campaigns:** while a campaign is a **draft**, its brand can attach **up to 2 photos or 1 video** (never both).
  Photos are JPG, PNG or WebP up to 5 MB; videos are MP4 or WebM up to 50 MB. API:
  `POST /api/v1/brand/campaigns/<id>/media/` (multipart field `file`) and `DELETE` on
  `.../media/<media_id>/`. Published and closed campaigns are frozen.
- **Profile pictures:** creators have a photo and brands a logo (JPG, PNG or WebP, up to 5 MB), set on **Edit
  profile** and saved as soon as the file is chosen. API: `PUT` or `DELETE` on
  `/api/v1/creators/me/photo/` and `/api/v1/brands/me/logo/`. A picture that is missing or fails to load shows the
  person's initials instead.
- The server decides what a file is by reading its first bytes, not its name, and stores it under a random name.
  Files are saved in `media/` (ignored by git) and served by Django in development only. Leave `MEDIA_ROOT` empty
  to use that folder. See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for production storage.

## Connecting YouTube (Google sign-in)

Only YouTube connects through OAuth. Instagram, TikTok and Facebook are manual entry and always labelled
Unverified (see the PRD for why). Connecting YouTube is also what makes a creator Verified.

1. In the [Google Cloud console](https://console.cloud.google.com/), create a project and enable the
   **YouTube Data API v3**.
2. Configure the **OAuth consent screen** in **Testing** mode and add your test users' Google accounts. The only
   scope used is `https://www.googleapis.com/auth/youtube.readonly`.
3. Create an **OAuth client ID** of type *Web application* and add the redirect URI
   `<backend-url>/api/v1/social/youtube/callback/` (locally `http://localhost:8000/api/v1/social/youtube/callback/`).
4. Put the client ID, secret and redirect URI in `.env` (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
   `GOOGLE_REDIRECT_URI`), and generate `OAUTH_ENCRYPTION_KEY` as shown in `.env.example`.
5. Set `FRONTEND_URL` to where the website runs (`http://localhost:5173` locally), because Google sends the
   browser back through it. Redis (or the in-memory cache above) must be available.

**How the connection finishes (for the frontend).** It takes three steps, so only the person who started it can
finish it:

1. `GET /api/v1/social/youtube/connect/` (logged in) returns the Google URL; send the browser there.
2. After consent, Google redirects the browser to the API's `/callback/`, which saves nothing and redirects on to
   `FRONTEND_URL/settings/connections?youtube=confirm&code=...&state=...` (or `?youtube=error&reason=access_denied|invalid_state`).
3. The frontend, logged in, sends both values unchanged to `POST /api/v1/social/youtube/complete/` with
   `{"state", "code"}`. It answers with the connection status, or a 400 whose `code` is `invalid_state`,
   `exchange_failed` or `no_refresh_token`.

**Disconnecting** deletes the stored tokens, revokes the grant at Google (best effort), and marks the creator's
YouTube stats Unverified, which also removes their right to apply.

**While the app is in Testing mode, Google expires refresh tokens after 7 days**, so creators may need to
reconnect about once a week. The creator gets a "reconnect" notification and their last known stats stay visible,
marked as outdated. Publishing the app (Google verification) removes the limit.

## Configuration

All configuration comes from environment variables; nothing secret is stored in the repository. Copy
`.env.example` to `.env` for local development (a test checks that the file lists every variable the settings read).

| Variable | Purpose |
|---|---|
| `DJANGO_SETTINGS_MODULE` | Which settings to run: `config.settings.dev` locally. Leave unset (production) on a server. |
| `SECRET_KEY` | Signs tokens and hashes reset codes. Long and random in production. |
| `ALLOWED_HOSTS` | Comma-separated host names the API answers to. |
| `DATABASE_URL` | PostgreSQL connection URL. |
| `REDIS_URL` | Redis for Celery and the shared cache (rate limiting, YouTube sign-in tokens). |
| `FRONTEND_URL` | Where the website runs. The YouTube callback redirects here and email links start with it. |
| `CORS_ALLOWED_ORIGINS` | Comma-separated website origins allowed to call the API (https in production). |
| `NUM_PROXIES` | Reverse proxies in front of the app, so rate limiting sees the real client IP. `0` in development, `1` in production by default. |
| `SECURE_SSL_REDIRECT` | Production only: redirect HTTP to HTTPS. Set `false` only for a plain-HTTP smoke test. |
| `SECURE_HSTS_SECONDS` | Production only: how long browsers must keep using HTTPS (default one year; try `300` first). |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | Production only, default `false`. Hard to undo. |
| `SECURE_HSTS_PRELOAD` | Production only, default `false`. Needs the option above; very hard to undo. |
| `OAUTH_ENCRYPTION_KEY` | Fernet key that encrypts stored YouTube tokens. Required in production. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | Google OAuth client (see above). |
| `YOUTUBE_API_KEY` | Optional server key for public video statistics. Without it, content performance shows `not_available`. |
| `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` | Email delivery: console in development, SMTP for real email. |
| `DEFAULT_FROM_EMAIL` | The sender address (set up SPF/DKIM for its domain). |
| `MEDIA_URL`, `MEDIA_ROOT` | URL and folder for uploaded files. `MEDIA_ROOT` empty means `<repo>/media`. |
| `CELERY_TASK_ALWAYS_EAGER` | Development only, default `True`: run background jobs inside the request. |

Settings modules: `config.settings.dev` (local), `config.settings.test` (pytest) and `config.settings.prod`
(deployment; it refuses to start with an unsafe configuration). **Production is the default**: `manage.py`, wsgi and
Celery start in production mode unless `DJANGO_SETTINGS_MODULE` says otherwise, so a server that forgets the
variable fails to start instead of running in debug mode. The `.env` you copy already selects development.

## How the API behaves

- **Auth:** `POST /api/v1/auth/login/` with `{"identifier", "password"}` (email or username), then send
  `Authorization: Bearer <token>`. Tokens last 24 hours. Logging out or resetting a password signs the user out
  everywhere.
- **Errors:** always `{"error": {"code", "message", "details"}}`. Branch on `code`.
- **Lists:** `count`, `next`, `previous`, `results`; `?page=` and `?page_size=` (max 50).
- **Roles:** creators and brands see different endpoints; the wrong role gets 403 and another account's data is 404.
- **Rate limits:** register 5/min, login 10/min, password reset 5/hour, email verify 20/hour, email resend 5/hour
  (and a 60-second wait between codes).

## Project layout

```
config/             settings (base / dev / test / prod), URLs, Celery
apps/core/          shared plumbing: error format, pagination, permissions, email queue, demo data
apps/accounts/      users, registration, login, password reset, email verification (brands)
apps/profiles/      creator and brand profiles, portfolio, creator directory
apps/social/        platform stats, YouTube sign-in and sync
apps/campaigns/     campaigns, their lifecycle, media and creator-facing discovery
apps/proposals/     applying, withdrawing, shortlist / accept / reject, deliverables
apps/reviews/       brand reviews of creators
apps/notifications/ in-app notifications and notification emails
apps/dashboards/    the creator and brand home screens
apps/adminpanel/    admin users, moderation and the audit log
frontend/           the React website
docs/               OpenAPI file, frontend guide, deployment guide, decisions
tests_e2e/          a standalone end-to-end script
```

Business rules live in each app's `services.py`; views stay thin.

## Troubleshooting

| Problem | Cause and fix |
|---|---|
| `docker compose` cannot connect, or "docker engine not running" | Docker Desktop is not running yet. Start it and wait until it says it is running, or use native PostgreSQL and Redis. |
| "Invalid line" warnings when the backend starts | `.env` has a blank line containing a space, or was saved with a byte-order mark. Save it as plain UTF-8 and remove blank-space lines. |
| Connecting YouTube returns 503 or an empty link | Redis is not reachable (see "Without Docker"), or the Google variables are empty. |
| After Google sign-in the browser lands on a dead page | `FRONTEND_URL` is wrong. Use `http://localhost:5173` in development. |
| No email arrives | With the console backend, read the code in the backend terminal. With SMTP, check the sender is verified at the provider. Brevo needs its SMTP login, not your account email; Resend without a verified domain only delivers to your own address. |
| A brand cannot publish or accept (403 `brand_email_unverified`) | Verify the email with the code (shown in the backend terminal in development). |
| A creator cannot apply (403 `creator_youtube_required`) | Connect YouTube. Manually typed stats do not count. |
| Uploaded pictures are missing | They live in `media/`. If you set `MEDIA_ROOT` yourself, keep the same folder between runs. |
| Tests cannot create a database | `DATABASE_URL` must name a PostgreSQL user that may create databases. |

## Known issues

- The endpoints `POST /api/v1/social/youtube/direct-connect/` and `POST /api/v1/social/direct-connect/<platform>/`
  mark stats as Verified from a handle and follower count the caller supplies, with no proof of ownership. They
  bypass the rule that only a real YouTube connection verifies a creator, and the website does not use them.
  Remove or protect them before any real use.

## Working on this repository

Work on a feature branch and open a pull request into `main`. When you change an endpoint, regenerate the API file
(a test fails if it is stale):

```bash
python manage.py spectacular --file docs/openapi.yml
```
