# Micro-Influencers' Platform: Backend

Django REST API for a two-sided creator / brand marketplace. The product spec is
[`PRD_Micro-Influencers_Platform.md`](PRD_Micro-Influencers_Platform.md); the build plan is
[`plan.md`](plan.md).

## Requirements

- Python 3.12 or newer
- Docker (PostgreSQL 16 and Redis 7), or your own PostgreSQL and Redis

Tests need a real PostgreSQL: the race-safe "accept" rule relies on row locks that SQLite does not provide.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements/dev.txt
cp .env.example .env               # then edit values
docker compose up -d db redis
python manage.py migrate
python manage.py runserver
```

Check it works: `GET http://localhost:8000/api/v1/health/` returns `{"status": "ok", "database": "ok"}`.

## Tests

```bash
pytest
```

Settings for tests are `config.settings.test` (set in `pytest.ini`). They read `DATABASE_URL`, so
point it at any PostgreSQL the test user may create databases on.

## Background workers

Email, YouTube syncs and campaign auto-closing run in Celery.

```bash
celery -A config worker --pool=solo -l info    # --pool=solo is required on Windows
celery -A config beat -l info                  # scheduled jobs
```

## Environment variables

All configuration comes from the environment; see [`.env.example`](.env.example). No secrets are
stored in the repository.

## Settings modules

| Module | Use |
|---|---|
| `config.settings.dev` | local development (default for `manage.py`) |
| `config.settings.test` | pytest |
| `config.settings.prod` | deployment; `SECRET_KEY` must be set |
