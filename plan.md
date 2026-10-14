# Micro-Influencers' Platform: Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the REST API for a two-sided creator / brand marketplace: auth, profiles, YouTube-verified stats, creator and campaign discovery, campaigns, a proposal pipeline with race-safe acceptance, dashboards and in-app notifications. Extensions (FR-20 to FR-24) follow only once the core is stable.

**Architecture:** One Django project with one app per domain (`accounts`, `profiles`, `social`, `campaigns`, `proposals`, `notifications`, `dashboards`, `core`). Business rules live in each app's `services.py`, and views stay thin. Slow or flaky work (email, YouTube sync, auto-closing campaigns) runs in Celery. The "accepted ≤ Creators Needed" rule is enforced in PostgreSQL with a row lock inside a transaction.

**Tech Stack:** Python 3.12, Django 5.2 LTS, Django REST Framework, `djangorestframework-simplejwt`, PostgreSQL 16, Celery + Redis, `cryptography` (Fernet), `drf-spectacular` (Swagger), `django-cors-headers`, `django-environ`, `requests`; tests with `pytest`, `pytest-django`, `factory_boy`, `responses`.

**Spec:** `PRD_Micro-Influencers_Platform.md` (v1.0), referenced below as FR-xx / section numbers.

**Assumptions to confirm:** (1) This repository is the backend repo and the Django project lives at its root. (2) Nothing of the PRD's week 1–2 backend work exists yet. If it does, mark those tasks done and start at the first unfinished one. (3) The PRD's week-3 date (Oct 12–16) is today, so the phases below are ordered by dependency and sized for four backend engineers working in parallel (see "Parallel Tracks").

## Global Constraints

Every task's requirements implicitly include these (values copied from the PRD).

- Roles at launch: `creator`, `brand`. `admin` exists as an enum value but has no endpoints until FR-22. Role is fixed at registration.
- Registration fields: Full Name, Email (unique), Username (unique), Password (minimum 8 characters), Mobile Number.
- JWT sessions; tokens expire after 24 hours; every route requires a valid token except the explicit public list in Task 23.
- Passwords use Django's default hasher. Plain-text passwords are never stored or logged.
- Reset code: 6 digits, expires after 10 minutes, single-use, invalid after 5 wrong attempts, stored hashed. Response is always "If this email is registered, a code has been sent." Resetting logs out existing sessions via a `token_version` on the user.
- Rate limiting on login, registration and password-reset endpoints.
- OAuth tokens encrypted at rest, never sent to the frontend. OAuth uses a `state` parameter and read-only minimum scopes. Disconnect deletes stored tokens.
- Only YouTube has OAuth. Instagram, TikTok and Facebook are manual entry, labelled Unverified.
- Portfolio: external URLs only, maximum 10 items per creator. Proposal portfolio links: up to 3.
- Creators Needed: whole number 1 to 20, default 1, enforced by a database check constraint.
- Campaign lifecycle is Draft → Published → Closed. Published campaigns cannot be edited or deleted. Closed cannot be reopened. A campaign does **not** auto-close when it is full.
- Accepted proposals never exceed Creators Needed under concurrent requests (transaction + row lock on the campaign). Full-campaign message: "All creators for this campaign have already been selected."
- Withdrawal reason for an Accepted proposal: required, up to 300 characters. Review text: up to 500 characters.
- Acceptance rate = proposals currently Accepted ÷ proposals sent (creator) or received (brand). Withdrawn counts as sent/received; Accepted-then-withdrawn does not count as accepted.
- Missing profile photo / logo: API returns `null` (the frontend draws the initials avatar).
- Lists are paginated and load within 3 seconds. Third-party API calls never run in the request path.
- All input validated and sanitised server-side. Secrets come from environment variables; none are hardcoded.
- Git: separate backend repo, one feature branch per phase (`feature/phase-N-<name>`), pull request into `main`.

## Review Focus

Failure modes the PRD implies but does not spell out. Each is pinned by a test tagged `(RF#)` in the owning task.

1. **RF1, deadline passed but the auto-close job has not run yet.** A creator must not be able to apply, and the campaign must not appear in discovery, in the window before the Celery job closes it. Pinned in Tasks 16 and 17.
2. **RF2, stored XSS through URLs and text.** `javascript:` and `data:` URLs in logo, photo, website, portfolio and proposal links are rejected. HTML in free-text fields is stripped. Pinned in Tasks 7, 9 and 17.
3. **RF3, cross-tenant access.** Brand A reading or acting on Brand B's campaign or proposals, or a creator reading another creator's proposals, gets 404 (never 200 or 403 leaking existence). Pinned in Tasks 15, 18, 19, 20.
4. **RF4, resubmission and double-submit edges.** Concurrent duplicate submissions create exactly one active proposal and return a clean 409 (not a 500). Resubmitting after rejection, or after withdrawal on a Closed campaign, is blocked. Pinned in Task 17.
5. **RF5, Google failures during sync.** A revoked token or API outage for one creator does not abort the batch, and does not erase the last known stats. Pinned in Task 13.

## Decisions the PRD Leaves Open

I chose these defaults; change any before the phase that uses it.

| # | Decision | Why |
|---|---|---|
| 1 | API prefix `/api/v1/`. Errors use one envelope: `{"error": {"code", "message", "details"}}` | Gives the frontend one error shape to handle |
| 2 | Login accepts email **or** username | PRD says "login" without naming the identifier |
| 3 | Logout bumps `token_version` (signs out all devices) | Reuses the reset mechanism; a stateless JWT cannot otherwise be revoked |
| 4 | Creators can open Published **and** Closed campaign detail; lists show only Published campaigns whose deadline is in the future | FR-12 implies a closed campaign can still be viewed; FR-11 lists only published |
| 5 | Disconnecting YouTube deletes tokens, keeps the last stats, and marks them Unverified | Verified must mean "currently linked" |
| 6 | Manual stats edits are rejected for a platform that is currently Verified | Prevents overwriting API data |
| 7 | Stats shown to brands (cards, proposals) come from the creator's primary platform | One definition everywhere; eligibility uses the campaign's platform |
| 8 | Acceptance rate is `null` when nothing was sent/received | Avoids division by zero and a misleading 0% |
| 9 | Manual YouTube refresh cooldown 15 min; daily sync 03:00 UTC; auto-close checked every 5 min | PRD says "cooldown" and "daily" without values |
| 10 | Shortlisting an already Shortlisted proposal returns 409; only Accept is idempotent | PRD defines idempotency only for Accept |
| 11 | Privacy Policy and Terms pages are frontend static content; no backend task | PRD §4.4 asks for pages, not endpoints |
| 12 | Extension only: a Completed collaboration cannot be withdrawn | "Completion is final" |

## Parallel Tracks (4 backend engineers)

After Phase 0, tracks can run in parallel; arrows are hard dependencies.

| Track | Phases | Starts after |
|---|---|---|
| A: Platform & auth | 0, 1 | none |
| B: Profiles & YouTube | 2, 4 | Task 4 (login) |
| C: Campaigns & discovery | 5 | Task 7 (profiles) and Task 10 (notifications) |
| D: Notifications, proposals, dashboards | 3, 6, 7 | Task 4, then Task 15 for proposals |

Phases 8 and 9 start only when Phases 0–7 are merged and green.

## File Structure

```
manage.py, pytest.ini, docker-compose.yml, Dockerfile, .env.example, README.md
requirements/{base,dev}.txt
config/{settings/{base,dev,prod,test}.py, urls.py, celery.py, wsgi.py}
apps/core/           exceptions, pagination, permissions, choices, validators, fields, emailing, health view
apps/accounts/       User, OneTimeCode, auth (register/login/logout/me), password reset, JWT with token_version
apps/profiles/       CreatorProfile, BrandProfile, PortfolioItem, completion indicator, creator directory
apps/social/         PlatformStats (manual + verified), YouTubeConnection, YouTubeClient, crypto, sync tasks
apps/campaigns/      Campaign, lifecycle services, creator-facing discovery/detail, auto-close task
apps/proposals/      Proposal, services (submit/shortlist/accept/reject/withdraw), brand + creator views
apps/notifications/  Notification, notify(), list/read endpoints
apps/dashboards/     creator + brand dashboard aggregation (read-only)
```

## API Surface (agree with frontend; Swagger is generated from the code in Task 2)

All under `/api/v1/`. "Any" = any authenticated user.

| Method + path | Role | FR |
|---|---|---|
| `POST auth/register/`, `POST auth/login/` | public | 01, 02 |
| `POST auth/logout/`, `GET auth/me/` | any | 02 |
| `POST auth/password-reset/request/`, `POST auth/password-reset/confirm/` | public | 02 |
| `GET, PATCH creators/me/` ; `GET, PATCH brands/me/` | creator ; brand | 03, 04 |
| `GET brands/{id}/` | creator | 04 |
| `GET creators/me/stats/`, `PUT creators/me/stats/{platform}/` | creator | 03, 05 |
| `GET, POST creators/me/portfolio/`, `DELETE creators/me/portfolio/{id}/` | creator | 06 |
| `GET social/youtube/`, `GET social/youtube/connect/`, `GET social/youtube/callback/`, `POST social/youtube/refresh/`, `DELETE social/youtube/`, `GET social/youtube/recent-content/` | creator (callback: signed `state`) | 05 |
| `GET creators/`, `GET creators/{id}/` | brand | 07, 08 |
| `GET, POST brand/campaigns/`, `GET, PATCH, DELETE brand/campaigns/{id}/`, `POST brand/campaigns/{id}/publish/`, `POST brand/campaigns/{id}/close/` | brand | 09, 10 |
| `GET campaigns/`, `GET campaigns/{id}/` | creator | 11, 12 |
| `POST campaigns/{id}/proposals/` | creator | 13 |
| `GET creators/me/proposals/`, `POST creators/me/proposals/{id}/withdraw/` | creator | 13, 16 |
| `GET brand/campaigns/{id}/proposals/` | brand | 14 |
| `POST brand/proposals/{id}/shortlist/`, `.../accept/`, `.../reject/` | brand | 15 |
| `GET notifications/`, `POST notifications/{id}/read/`, `POST notifications/read-all/` | any | 19 |
| `GET creators/me/dashboard/`, `GET brands/me/dashboard/` | creator ; brand | 17, 18 |

Task conventions: every task is test-first (write tests → see them fail → implement → see them pass → commit). Test commands run from the repo root against PostgreSQL (`docker compose up -d db redis`). Tests that prove locking need real PostgreSQL, so SQLite is not used anywhere.

---

# Phase 0: Foundation (Track A)

### Task 1: Project scaffold, settings, CI-ready test setup

**Files:**
- Create: `manage.py`, `config/settings/{base,dev,prod,test}.py`, `config/{urls,celery,wsgi}.py`, `apps/core/{__init__,apps,views}.py`, `requirements/{base,dev}.txt`, `docker-compose.yml`, `.env.example`, `.gitignore`, `pytest.ini`, `README.md`
- Test: `apps/core/tests/test_health.py`

**Interfaces:**
- Produces: settings module `config.settings.test` (PostgreSQL via `DATABASE_URL`, `CELERY_TASK_ALWAYS_EAGER=True`, locmem cache and email backend, fast password hasher for tests only); DRF default permission `IsAuthenticated` (so every new view is protected unless it opts out); `GET /api/v1/health/` (public). Celery app in `config/celery.py` exposed as `config.celery.app`. Env vars documented in `.env.example`: `SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS`, `OAUTH_ENCRYPTION_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `EMAIL_*`.

- [ ] **Step 1: Write the failing test** `test_health_ok_without_auth`: `GET /api/v1/health/` → 200 and JSON `{"status": "ok", "database": "ok"}`. `test_unlisted_route_requires_auth`: a throwaway `APIView` with no permission override returns 401 with no token.
- [ ] **Step 2: Run** `pytest apps/core/tests/test_health.py -v` → FAIL (404 / no module).
- [ ] **Step 3: Implement** the scaffold; `HealthView` runs `SELECT 1`. README documents `docker compose up -d db redis`, migrate, `pytest`, running `celery -A config worker --pool=solo` (needed on Windows) and `celery -A config beat`.
- [ ] **Step 4: Run** the same command → PASS.
- [ ] **Step 5: Commit** `git commit -m "chore: django project scaffold with postgres, celery, pytest"`

### Task 2: Shared API plumbing (errors, pagination, permissions, safe input, Swagger)

**Files:**
- Create: `apps/core/{exceptions,pagination,permissions,choices,validators,fields}.py`
- Modify: `config/settings/base.py` (`EXCEPTION_HANDLER`, `DEFAULT_PAGINATION_CLASS`, `SPECTACULAR_SETTINGS`), `config/urls.py` (`/api/schema/`, `/api/docs/`)
- Test: `apps/core/tests/{test_exceptions,test_validators,test_fields,test_pagination}.py`

**Interfaces:**
- Produces:
  - `DomainError(APIException)` with class attrs `status_code`, `default_code`, `default_detail`; `Conflict(DomainError)` = 409.
  - `api_exception_handler(exc, context) -> Response` returning `{"error": {"code": str, "message": str, "details": dict | list | None}}` for DRF, Django `Http404` and `DomainError`.
  - `StandardPagination(PageNumberPagination)`: `page_size=20`, `page_size_query_param="page_size"`, `max_page_size=50`.
  - `IsCreator`, `IsBrand`, `IsAdminRole` (`BasePermission`; read `request.user.role`; false when unauthenticated).
  - `Niche` and `Platform` (`TextChoices`). `Niche`: fitness, tech, beauty, food, travel, other. `Platform`: instagram, youtube, tiktok, facebook.
  - `validate_safe_url(value: str) -> None` accepts only `http`/`https` with a host; raises `ValidationError` otherwise.
  - `SafeCharField(serializers.CharField)`: strips HTML tags (`django.utils.html.strip_tags`) and surrounding whitespace.

- [ ] **Step 1: Write the failing tests:** `test_domain_error_uses_envelope` (409 body has `error.code == "conflict"`); `test_validation_error_has_details_per_field`; `test_404_uses_envelope`; `test_validate_safe_url_rejects` for `javascript:alert(1)`, `data:text/html,x`, `ftp://x.com`, `//x.com`, and accepts `https://example.com/a?b=1`; `test_safe_char_field_strips_tags` (`"<script>x</script>hi"` → `"xhi"`); `test_pagination_caps_page_size_at_50`; `test_roles_permission` for each role with a stub user.
- [ ] **Step 2: Run** `pytest apps/core -v` → FAIL.
- [ ] **Step 3: Implement** the modules above; configure `drf-spectacular` so `GET /api/docs/` serves Swagger UI.
- [ ] **Step 4: Run** `pytest apps/core -v` → PASS; `python manage.py spectacular --file schema.yml --validate` exits 0.
- [ ] **Step 5: Commit** `git commit -m "feat(core): error envelope, pagination, permissions, safe input, swagger"`

---

# Phase 1: Authentication & Access, FR-01, FR-02 (Track A)

### Task 3: User model and registration (FR-01)

**Files:**
- Create: `apps/accounts/{models,serializers,services,views,urls}.py`, `apps/accounts/tests/{factories,test_register}.py`
- Modify: `config/settings/base.py` (`AUTH_USER_MODEL = "accounts.User"`), `config/urls.py`

**Interfaces:**
- Produces:
  - `Role(TextChoices)`: `CREATOR="creator"`, `BRAND="brand"`, `ADMIN="admin"`.
  - `User(AbstractUser)` + `full_name: CharField(150)`, `mobile_number: CharField(20)`, `role: CharField(choices=Role)`, `token_version: PositiveIntegerField(default=0)`. Email stored lowercased with a unique `Lower("email")` constraint; username unique.
  - `register_user(*, role: str, full_name: str, email: str, username: str, password: str, mobile_number: str) -> User` in `apps/accounts/services.py`. Role `admin` is rejected here.
  - `POST /api/v1/auth/register/` → 201 with user fields (no token). Throttle scope `register`.
  - `UserFactory(role=...)` in `apps/accounts/tests/factories.py` (used by every later task).

- [ ] **Step 1: Write the failing tests:** `test_register_creator_returns_201_without_password`; `test_register_requires_role_before_details` (missing role → 400 with `details.role`); `test_password_shorter_than_8_rejected`; `test_duplicate_email_case_insensitive_rejected` (`A@x.com` vs `a@x.com`); `test_duplicate_username_rejected`; `test_admin_role_not_registrable`; `test_password_is_hashed` (stored value starts with `pbkdf2_`); `test_mobile_number_format` (`+8801712345678` ok, `abc` rejected); `test_register_is_throttled` (the 6th request in a minute → 429).
- [ ] **Step 2: Run** `pytest apps/accounts/tests/test_register.py -v` → FAIL.
- [ ] **Step 3: Implement** model + migration, `register_user`, serializer (mobile validated against `^\+?[0-9]{7,15}$`, `full_name` via `SafeCharField`), view, `register: 5/min` throttle rate.
- [ ] **Step 4: Run** the same command → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(accounts): user model and registration (FR-01)"`

### Task 4: Login, logout, `me`, versioned JWT (FR-02)

**Files:**
- Create: `apps/accounts/authentication.py`, `apps/accounts/tests/test_login.py`
- Modify: `apps/accounts/{services,views,urls}.py`, `config/settings/base.py` (`SIMPLE_JWT` access lifetime 24h, `DEFAULT_AUTHENTICATION_CLASSES`)

**Interfaces:**
- Consumes: `User`, `UserFactory` (Task 3).
- Produces:
  - `authenticate_login(identifier: str, password: str) -> User` (email or username, case-insensitive for email); raises `InvalidCredentials` (401, code `invalid_credentials`, message "Invalid email/username or password.").
  - `issue_access_token(user: User) -> str` with claim `tv` = `user.token_version`.
  - `VersionedJWTAuthentication(JWTAuthentication)`: rejects tokens whose `tv` ≠ `user.token_version`, and inactive users.
  - `POST auth/login/` → `{"access": str, "user": {id, full_name, email, username, role}}`; throttle scope `login` (10/min). `POST auth/logout/` → 204 and increments `token_version`. `GET auth/me/`.

- [ ] **Step 1: Write the failing tests:** `test_login_with_email_and_with_username`; `test_login_returns_role_for_routing` (creator → `"creator"`, brand → `"brand"`); `test_wrong_password_returns_clear_error` (401, same body for unknown user); `test_token_lifetime_is_24_hours` (decode `exp - iat == 86400`); `test_protected_route_without_token_is_401`; `test_token_with_old_token_version_rejected`; `test_logout_invalidates_token` (token works on `me`, 204 on logout, 401 on `me` after); `test_login_throttled`; `test_inactive_user_cannot_login`.
- [ ] **Step 2: Run** `pytest apps/accounts/tests/test_login.py -v` → FAIL.
- [ ] **Step 3: Implement** with SimpleJWT: custom token class adding `tv`; authentication class compares claim to DB value.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(accounts): login, logout, me with versioned JWT (FR-02)"`

### Task 5: Email service on Celery

**Files:**
- Create: `apps/core/emailing.py`, `apps/core/templates/email/{password_reset}.txt`, `apps/core/tests/test_emailing.py`

**Interfaces:**
- Produces:
  - `queue_email(to: str, subject: str, template: str, context: dict) -> None`: renders `email/<template>.txt` and enqueues the task. Never raises into the caller.
  - Celery task `deliver_email(to: str, subject: str, body: str) -> None`: sends via `django.core.mail.send_mail`; any exception is logged (`logger.exception`) and swallowed in the core version (FR-24 adds retry in Task 26).
  - Env-driven `EMAIL_BACKEND`, `EMAIL_HOST*`, `DEFAULT_FROM_EMAIL` (provider is SMTP-compatible so the team can use any provider; configure SPF/DKIM on the sender domain).

- [ ] **Step 1: Write the failing tests:** `test_queue_email_sends_via_backend` (locmem outbox has 1 message with the rendered body); `test_provider_failure_is_logged_not_raised` (patch `send_mail` to raise `SMTPException`; `queue_email` returns normally; `caplog` has the error); `test_queue_email_swallows_broker_error` (patch `.delay` to raise; no exception).
- [ ] **Step 2: Run** `pytest apps/core/tests/test_emailing.py -v` → FAIL.
- [ ] **Step 3: Implement** the module and the template.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(core): background email service"`

### Task 6: Password reset with one-time codes (FR-02)

**Files:**
- Create: `apps/accounts/codes.py`, `apps/accounts/tests/test_password_reset.py`
- Modify: `apps/accounts/{models,services,views,urls}.py`

**Interfaces:**
- Consumes: `queue_email` (Task 5), `User.token_version` (Task 3).
- Produces:
  - `OneTimeCode(user FK, purpose, code_hash, expires_at, used_at null, attempts smallint default 0, created_at)`; `purpose` is a `TextChoices` with `PASSWORD_RESET="password_reset"` and `EMAIL_VERIFICATION="email_verification"` (the second is for Task 26).
  - `codes.issue_code(user: User, purpose: str) -> str`: generates a 6-digit code with `secrets`, voids any unused earlier code for that user and purpose, stores an HMAC-SHA256 hash (key `SECRET_KEY`), expires in 10 minutes, returns the plaintext once.
  - `codes.verify_code(user: User, purpose: str, code: str) -> None`: raises `CodeInvalid` (400 `invalid_reset_code`), `CodeExpired` (400 `reset_code_expired`), `CodeUsed` (400 `reset_code_used`), `CodeLocked` (400 `reset_code_locked`, after 5 wrong attempts). Uses `hmac.compare_digest`; increments `attempts` on each wrong code.
  - `request_password_reset(email: str) -> None`; `confirm_password_reset(email: str, code: str, new_password: str) -> None` (sets password, increments `token_version`, marks the code used). Unknown email on confirm raises `CodeInvalid`.
  - `POST auth/password-reset/request/` always → 200 `{"detail": "If this email is registered, a code has been sent."}`; throttle scope `password_reset` (5/hour per IP). `POST auth/password-reset/confirm/` (throttle scope `password_reset_confirm`, 10/hour per IP).

- [ ] **Step 1: Write the failing tests:** `test_request_registered_email_sends_one_email_with_6_digit_code`; `test_request_unregistered_email_same_response_and_no_email` (assert identical status and body, outbox empty); `test_provider_down_still_returns_same_message` (patch `send_mail` to raise); `test_correct_code_changes_password_and_old_stops_working`; `test_expired_code_rejected` (freeze time +10 min 1 s); `test_used_code_rejected`; `test_five_wrong_attempts_lock_the_code` (6th attempt with the correct code → `reset_code_locked`); `test_code_stored_hashed` (plaintext not in DB); `test_reset_logs_out_existing_sessions` (old token → 401); `test_new_code_voids_previous_code`; `test_new_password_min_8_enforced`; `test_email_matching_ignores_case_and_whitespace`.
- [ ] **Step 2: Run** `pytest apps/accounts/tests/test_password_reset.py -v` → FAIL.
- [ ] **Step 3: Implement** the model/migration, `codes.py`, services and views. Enqueue the email inside `transaction.on_commit`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(accounts): password reset via emailed one-time code (FR-02)"`

---

# Phase 2: Profiles & Stats, FR-03, FR-04, FR-06 (Track B)

### Task 7: Creator and brand profiles (FR-03, FR-04)

**Files:**
- Create: `apps/profiles/{models,serializers,services,views,urls}.py`, `apps/profiles/tests/{test_creator_profile,test_brand_profile}.py`
- Modify: `config/urls.py`

**Interfaces:**
- Consumes: `IsCreator`, `IsBrand`, `SafeCharField`, `validate_safe_url`, `Niche`, `Platform` (Task 2); `UserFactory` (Task 3).
- Produces:
  - `CreatorProfile(user OneToOne, photo_url null, bio, niche, primary_platform, city, country, rate_post, rate_story, rate_video)` (rates `DecimalField(10,2)`, nullable, ≥ 0). `BrandProfile(user OneToOne, company_name, industry, website, logo_url null, about)`. Profiles are created lazily by `get_or_create_profile(user) -> CreatorProfile | BrandProfile`.
  - `completion_percent(profile: CreatorProfile) -> int`: 8 equally weighted items: photo, bio, niche, primary platform, location (city **and** country), any rate, stats on the primary platform, at least one portfolio item. Returns `round(100 * done / 8)`.
  - `GET, PATCH creators/me/` (includes `completion_percent`); `GET, PATCH brands/me/`; `GET brands/{id}/` (creator-only).
  - A blank `photo_url`/`logo_url` is stored and returned as `null`.

- [ ] **Step 1: Write the failing tests:** `test_new_creator_profile_is_empty_with_0_percent`; `test_completion_percent_exact_values` (empty → 0, photo+bio+niche+platform → 50, everything → 100; the stats and portfolio items are asserted again in Tasks 8 and 9); `test_patch_updates_only_own_profile`; `test_blank_photo_url_returns_null`; `test_javascript_photo_url_rejected` and `test_javascript_website_and_logo_rejected` **(RF2)**; `test_html_in_bio_and_about_is_stripped` **(RF2)**; `test_negative_rate_rejected`; `test_brand_cannot_use_creator_endpoint_403`; `test_creator_can_view_brand_profile_by_id`; `test_brand_cannot_view_brand_profile_by_id_403` ; `test_unauthenticated_brand_profile_401`.
- [ ] **Step 2: Run** `pytest apps/profiles -v` → FAIL.
- [ ] **Step 3: Implement** models/migration, serializers using `SafeCharField` and `validate_safe_url`, views.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(profiles): creator and brand profiles (FR-03, FR-04)"`

### Task 8: Platform stats with manual entry (FR-03, FR-05 fallback)

**Files:**
- Create: `apps/social/{models,serializers,services,views,urls,queries}.py`, `apps/social/tests/{test_stats,test_queries}.py`
- Modify: `apps/profiles/serializers.py` (embed `stats` in creator profile), `config/urls.py`

**Interfaces:**
- Consumes: `Platform` (Task 2), `CreatorProfile` (Task 7).
- Produces:
  - `PlatformStats(creator FK User, platform, handle_url null, followers PositiveInteger, engagement_rate Decimal(5,2), is_verified bool=False, is_outdated bool=False, last_synced_at, updated_at)`; unique `(creator, platform)`.
  - `set_manual_stats(*, creator: User, platform: str, followers: int, engagement_rate: Decimal, handle_url: str | None) -> PlatformStats`: raises `Conflict` (code `stats_verified`) when the existing row `is_verified`. Always `is_verified=False`, `last_synced_at=now()`.
  - `annotate_primary_stats(qs: QuerySet[CreatorProfile]) -> QuerySet`: adds `primary_followers`, `primary_engagement`, `primary_verified` via `Subquery` on the profile's `primary_platform`. Reused by Tasks 10, 18, 21.
  - `GET creators/me/stats/` → list; `PUT creators/me/stats/{platform}/`. Each stat serialises `is_verified`, `is_outdated`, `last_synced_at`.

- [ ] **Step 1: Write the failing tests:** `test_manual_entry_creates_unverified_stat`; `test_manual_entry_updates_existing_unverified`; `test_manual_entry_blocked_on_verified_platform_409`; `test_engagement_rate_range_0_to_100`; `test_followers_cannot_be_negative`; `test_unknown_platform_404`; `test_annotate_primary_stats_uses_primary_platform_only` (two stats rows, only the primary one is returned); `test_completion_percent_counts_primary_platform_stats`.
- [ ] **Step 2: Run** `pytest apps/social -v` → FAIL.
- [ ] **Step 3: Implement** models/migration, service, queries, views; extend `completion_percent` input to count the stats item.
- [ ] **Step 4: Run** `pytest apps/social apps/profiles -v` → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(social): platform stats with manual entry fallback"`

### Task 9: Portfolio (FR-06)

**Files:**
- Create: `apps/profiles/tests/test_portfolio.py`
- Modify: `apps/profiles/{models,serializers,services,views,urls}.py`

**Interfaces:**
- Produces: `PortfolioItem(creator FK User, url, caption(200), source {"manual","youtube"}, created_at)`; `add_portfolio_item(*, creator: User, url: str, caption: str, source: str = "manual") -> PortfolioItem` (raises `Conflict` code `portfolio_full` at 10 items, with the count taken under `select_for_update` on the creator's profile row); `GET, POST creators/me/portfolio/`; `DELETE creators/me/portfolio/{id}/` (own items only).

- [ ] **Step 1: Write the failing tests:** `test_add_item_with_url_and_caption`; `test_eleventh_item_rejected_409`; `test_delete_frees_a_slot`; `test_cannot_delete_other_creators_item_404`; `test_javascript_url_rejected` and `test_html_caption_stripped` **(RF2)**; `test_brand_cannot_add_403`; `test_ten_parallel_adds_never_exceed_ten` (transactional test, 12 threads).
- [ ] **Step 2: Run** `pytest apps/profiles/tests/test_portfolio.py -v` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(profiles): portfolio items (FR-06)"`

---

# Phase 3: Notifications (Track D)

### Task 10: In-app notification service and API (FR-19)

**Files:**
- Create: `apps/notifications/{models,serializers,services,views,urls}.py`, `apps/notifications/tests/test_notifications.py`
- Modify: `config/urls.py`

**Interfaces:**
- Produces:
  - `Kind(TextChoices)`: `PROPOSAL_SHORTLISTED`, `PROPOSAL_ACCEPTED`, `PROPOSAL_REJECTED`, `ACCOUNT_RECONNECT`, `PROPOSAL_RECEIVED`, `PROPOSAL_WITHDRAWN`, `CAMPAIGN_AUTO_CLOSED`.
  - `Notification(user FK, kind, message(255), payload JSON default {}, is_read bool=False, created_at)`; index on `(user, is_read, -created_at)`.
  - `notify(user: User, kind: str, message: str, **payload) -> Notification` in `services.py`. Single entry point; Task 26 hooks email onto it.
  - `GET notifications/` → paginated newest first plus top-level `unread_count`; `POST notifications/{id}/read/` (own only, idempotent); `POST notifications/read-all/`.

- [ ] **Step 1: Write the failing tests:** `test_notify_creates_unread_notification_with_payload`; `test_list_returns_newest_first_and_unread_count`; `test_mark_read_only_for_owner_404_otherwise`; `test_mark_read_is_idempotent`; `test_read_all_marks_only_my_notifications`; `test_notifications_require_auth`.
- [ ] **Step 2: Run** `pytest apps/notifications -v` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(notifications): in-app notifications (FR-19)"`

---

# Phase 4: YouTube Integration, FR-05 (Track B)

### Task 11: Token encryption, YouTube client, connection model

**Files:**
- Create: `apps/social/{crypto,youtube_client}.py`, `apps/social/tests/{test_crypto,test_youtube_client}.py`
- Modify: `apps/social/models.py`

**Interfaces:**
- Produces:
  - `encrypt(plain: str) -> str`, `decrypt(token: str) -> str` (Fernet; key `OAUTH_ENCRYPTION_KEY`).
  - `YouTubeConnection(creator OneToOne User, access_token_enc, refresh_token_enc, access_expires_at, status {"connected","needs_reconnect"}, recent_content JSON default [], last_manual_refresh_at null, connected_at)`. Tokens are never exposed by any serializer.
  - `YouTubeClient` with: `build_auth_url(state: str) -> str` (scope `https://www.googleapis.com/auth/youtube.readonly`, `access_type=offline`, `prompt=consent`); `exchange_code(code: str) -> TokenSet`; `refresh_access_token(refresh_token: str) -> TokenSet`; `fetch_channel(access_token: str) -> ChannelSnapshot`.
  - Dataclasses `TokenSet(access_token, refresh_token | None, expires_in)` and `ChannelSnapshot(handle_url, subscribers: int, engagement_rate: Decimal, recent_content: list[dict])`. Engagement rate = (sum of likes + comments) ÷ (sum of views) × 100 over the last 10 uploads, rounded to 2 places; 0 when views are 0. `recent_content` items: `{video_id, title, url, published_at}`.
  - Exceptions: `TokenRevoked` (Google `invalid_grant` or 401), `TransientApiError` (5xx, timeouts, 429), `QuotaExceeded(TransientApiError)`.

- [ ] **Step 1: Write the failing tests:** `test_encrypt_roundtrip_and_ciphertext_differs`; `test_decrypt_with_wrong_key_raises`; `test_auth_url_has_readonly_scope_and_state`; `test_fetch_channel_computes_engagement_rate` (with `responses` mocking 10 videos, assert exact Decimal); `test_zero_views_gives_zero_engagement`; `test_invalid_grant_raises_token_revoked`; `test_503_raises_transient`; `test_quota_error_raises_quota_exceeded`; `test_connection_serializer_never_contains_tokens`.
- [ ] **Step 2: Run** `pytest apps/social/tests/test_crypto.py apps/social/tests/test_youtube_client.py -v` → FAIL.
- [ ] **Step 3: Implement.** All HTTP goes through one `requests.Session` wrapper with a 10 s timeout.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(social): encrypted token storage and YouTube API client"`

### Task 12: OAuth connect, callback, disconnect, recent content (FR-05)

**Files:**
- Create: `apps/social/tests/test_youtube_oauth.py`
- Modify: `apps/social/{services,views,urls}.py`

**Interfaces:**
- Consumes: `YouTubeClient`, `YouTubeConnection`, `encrypt` (Task 11); `PlatformStats` (Task 8).
- Produces:
  - `start_connect(user: User) -> str` returns the Google URL. `state = signing.dumps({"uid": user.id, "nonce": str}, salt="youtube-oauth")`, nonce cached for 10 minutes and deleted on use (single-use).
  - `complete_connect(*, state: str, code: str) -> PlatformStats`: verifies `state` (max age 600 s, nonce still cached), exchanges the code, stores encrypted tokens, upserts `PlatformStats(platform="youtube", is_verified=True)`, then enqueues `sync_connection_task` (Task 13).
  - `disconnect(user: User) -> None`: deletes the `YouTubeConnection` row (and so the tokens); stats are kept with `is_verified=False`.
  - `GET social/youtube/` → `{connected, status, last_synced_at, is_outdated}`; `GET social/youtube/connect/` → `{"authorization_url": str}`; `GET social/youtube/callback/?code&state` → 302 to `FRONTEND_URL/settings/connections?youtube=success|error`; `DELETE social/youtube/` → 204; `GET social/youtube/recent-content/` → cached list.

- [ ] **Step 1: Write the failing tests:** `test_connect_returns_google_url_with_state`; `test_callback_with_valid_state_stores_encrypted_tokens_and_verified_stats` (DB values ≠ plaintext; client mocked); `test_callback_with_tampered_state_redirects_error_and_stores_nothing`; `test_callback_state_cannot_be_reused`; `test_callback_expired_state_rejected` (freeze time +601 s); `test_user_denied_consent_redirects_error`; `test_disconnect_deletes_tokens_keeps_stats_unverified`; `test_brand_cannot_connect_403`; `test_callback_is_reachable_without_auth_header`.
- [ ] **Step 2: Run** `pytest apps/social/tests/test_youtube_oauth.py -v` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(social): youtube oauth connect and disconnect (FR-05)"`

### Task 13: Stats sync, daily schedule, manual refresh, failure handling (FR-05)

**Files:**
- Create: `apps/social/tasks.py`, `apps/social/tests/test_youtube_sync.py`
- Modify: `apps/social/{services,views,urls}.py`, `config/settings/base.py` (`CELERY_BEAT_SCHEDULE`: `sync_all_youtube` daily 03:00 UTC)

**Interfaces:**
- Consumes: `YouTubeClient` and its exceptions (Task 11), `notify` and `Kind` (Task 10).
- Produces:
  - `sync_connection(connection: YouTubeConnection) -> None`: refreshes the access token when expired, fetches the channel, updates `PlatformStats` (followers, engagement, `is_outdated=False`, `last_synced_at=now()`), stores `recent_content`. On `TokenRevoked`: sets `status="needs_reconnect"`, marks stats `is_outdated=True`, keeps the old numbers, and calls `notify(creator, Kind.ACCOUNT_RECONNECT, ...)` **only on the transition** from `connected` (once per failure, not daily). On `TransientApiError`: re-raises for Celery retry and leaves stats untouched.
  - Celery tasks: `sync_connection_task(connection_id: int)` (`autoretry_for=(TransientApiError,)`, `retry_backoff=True`, `max_retries=5`); `sync_all_youtube()` (iterates connected rows, enqueues one task each, isolates failures).
  - `request_manual_refresh(user: User) -> None`: raises `DomainError` code `refresh_cooldown` (429) within `YOUTUBE_REFRESH_COOLDOWN_SECONDS = 900`, else stamps `last_manual_refresh_at` and enqueues. `POST social/youtube/refresh/` → 202.

- [ ] **Step 1: Write the failing tests:** `test_sync_updates_followers_engagement_and_last_synced`; `test_expired_access_token_is_refreshed_first`; `test_revoked_token_marks_needs_reconnect_keeps_stats_outdated_and_notifies_once` **(RF5)**; `test_second_failed_sync_does_not_notify_again` **(RF5)**; `test_transient_error_leaves_stats_untouched_and_retries` **(RF5)**; `test_sync_all_continues_after_one_creator_fails` **(RF5)** (three connections, the middle one raises); `test_manual_refresh_within_cooldown_429`; `test_manual_refresh_after_cooldown_202`; `test_beat_schedule_contains_daily_sync`; `test_reconnect_after_revocation_restores_connected_status`.
- [ ] **Step 2: Run** `pytest apps/social/tests/test_youtube_sync.py -v` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest apps/social -v` → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(social): scheduled youtube sync with revocation handling (FR-05)"`

---

# Phase 5: Discovery & Campaigns, FR-07 to FR-12 (Track C)

### Task 14: Creator directory and creator profile view (FR-07, FR-08)

**Files:**
- Create: `apps/profiles/{filters,directory_views}.py`, `apps/profiles/tests/test_directory.py`
- Modify: `apps/profiles/urls.py`

**Interfaces:**
- Consumes: `annotate_primary_stats` (Task 8), `IsBrand`, `StandardPagination`.
- Produces:
  - `GET creators/` (brand-only, paginated). Query params: `q` (name or username, case-insensitive), `niche`, `platform`, `min_followers`, `max_followers`, `min_engagement`, `max_engagement`, `location` (matches city or country), `min_rate`, `max_rate` (any of the three rates), `verified_only=true`, `ordering` ∈ {`followers`,`engagement`,`rate`} with optional `-`. Card fields: id, name, photo_url, niche, primary platform, followers, engagement_rate, is_verified.
  - `GET creators/{id}/` (brand-only): full profile, per-platform stats with `is_verified`, `is_outdated`, `last_synced_at`, rate card, portfolio items.

- [ ] **Step 1: Write the failing tests:** one per filter (`test_filter_by_niche`, `..._platform`, `..._follower_range`, `..._engagement_range`, `..._location`, `..._rate_range`, `..._verified_only`, `..._keyword_matches_name_and_username`); `test_filters_combine_with_and`; `test_sort_by_followers_desc_and_rate_asc`; `test_pagination_page_size_and_cap`; `test_creator_without_stats_still_listed_and_sorts_last`; `test_creator_role_gets_403`; `test_logged_out_gets_401_for_list_and_detail`; `test_detail_includes_portfolio_and_stats_labels`; `test_unknown_creator_404`; `test_list_uses_constant_query_count` (`django_assert_max_num_queries(6)` for 30 creators).
- [ ] **Step 2: Run** `pytest apps/profiles/tests/test_directory.py -v` → FAIL.
- [ ] **Step 3: Implement** filters as plain queryset functions in `filters.py`; keep `annotate_primary_stats` as the single source of followers/engagement.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(profiles): creator directory and profile view (FR-07, FR-08)"`

### Task 15: Campaign model and brand lifecycle (FR-09, FR-10)

**Files:**
- Create: `apps/campaigns/{models,serializers,services,tasks,views,urls}.py`, `apps/campaigns/tests/{factories,test_brand_campaigns,test_lifecycle,test_autoclose}.py`
- Modify: `config/settings/base.py` (beat: `close_expired_campaigns` every 5 minutes), `config/urls.py`

**Interfaces:**
- Consumes: `notify`, `Kind.CAMPAIGN_AUTO_CLOSED` (Task 10); `IsBrand`; `Niche`, `Platform`.
- Produces:
  - `Campaign(brand FK User, title, description, niche, platform, budget Decimal(10,2) > 0, deadline DateTime, deliverables Text, creators_needed SmallInt default 1, min_followers null, status {"draft","published","closed"} default "draft", published_at null, closed_at null, created_at)` with `CheckConstraint(creators_needed BETWEEN 1 AND 20, name="campaign_creators_needed_1_20")`. `CampaignFactory` for later tasks.
  - `publish_campaign(campaign: Campaign) -> Campaign` (Draft only; deadline must be in the future); `close_campaign(campaign: Campaign, *, auto: bool = False) -> Campaign` (Published only; idempotent for already Closed returns unchanged); `close_expired_campaigns() -> int` (Celery task and function; closes Published rows with `deadline <= now()`, notifies each brand once).
  - Errors: `Conflict` codes `campaign_not_editable` (edit/delete when not Draft), `invalid_campaign_transition`.
  - Endpoints: `GET, POST brand/campaigns/` (own campaigns, all statuses, filter `status`), `GET, PATCH, DELETE brand/campaigns/{id}/`, `POST .../publish/`, `POST .../close/`.

- [ ] **Step 1: Write the failing tests:** `test_create_defaults_to_draft_and_creators_needed_1`; `test_creators_needed_0_and_21_rejected_by_serializer`; `test_db_check_constraint_blocks_21` (bypass serializer with `Campaign.objects.create`); `test_budget_must_be_positive`; `test_draft_can_be_edited_and_deleted`; `test_published_cannot_be_edited_or_deleted_409`; `test_publish_requires_future_deadline`; `test_close_published_ok_and_closed_cannot_reopen`; `test_close_draft_is_invalid_transition`; `test_auto_close_closes_only_expired_published_and_notifies_brand_once`; `test_auto_close_second_run_creates_no_duplicate_notification`; `test_brand_sees_only_own_campaigns`; `test_other_brands_campaign_returns_404_for_get_patch_delete_publish_close` **(RF3)**; `test_creator_role_403`; `test_html_in_title_and_description_stripped` **(RF2)**.
- [ ] **Step 2: Run** `pytest apps/campaigns -v` → FAIL.
- [ ] **Step 3: Implement.** `brand` scoping happens in `get_queryset` so foreign ids give 404.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(campaigns): campaign model and draft/publish/close lifecycle (FR-09, FR-10)"`

### Task 16: Creator-facing campaign discovery and detail (FR-11, FR-12)

**Files:**
- Create: `apps/campaigns/{discovery,eligibility}.py`, `apps/campaigns/tests/{test_discovery,test_eligibility}.py`
- Modify: `apps/campaigns/{serializers,urls}.py`

**Interfaces:**
- Consumes: `PlatformStats` (Task 8), `Campaign` (Task 15), `BrandProfile` (Task 7).
- Produces:
  - `is_eligible(campaign: Campaign, followers_by_platform: dict[str, int]) -> bool`: true when the campaign's platform is in the dict and (`min_followers` is null or followers ≥ it). Unverified counts. Informational only.
  - `GET campaigns/` (creator-only, paginated): only `status="published"` **and** `deadline > now()` **(RF1)**. Filters: `niche`, `platform`, `min_budget`, `max_budget`, `deadline_before`, `deadline_after`, `q` (title/description). Card: id, title, brand `{id, name, logo_url}`, niche, budget, platform, deadline, creators_needed, `eligible`.
  - `GET campaigns/{id}/` (creator-only): full details for Published **and** Closed campaigns, 404 for Draft. Brand block links to `brands/{id}/`. Fields added in Task 17 (`accepted_count`, `all_creators_selected`, `can_apply`, `apply_blocked_reason`).

- [ ] **Step 1: Write the failing tests:** `test_draft_and_closed_not_listed`; `test_expired_but_unclosed_campaign_not_listed` **(RF1)**; each filter has a test; `test_keyword_search`; `test_eligible_true_when_platform_stat_and_followers_meet_minimum`; `test_eligible_false_without_stat_for_platform`; `test_eligible_false_below_minimum`; `test_unverified_stats_count_as_eligible`; `test_eligible_true_when_no_minimum_set`; `test_draft_detail_404`; `test_closed_detail_visible`; `test_brand_role_403_and_logged_out_401`; `test_list_query_count_is_constant` (`django_assert_max_num_queries(6)` for 30 campaigns).
- [ ] **Step 2: Run** `pytest apps/campaigns/tests/test_discovery.py apps/campaigns/tests/test_eligibility.py -v` → FAIL.
- [ ] **Step 3: Implement.** Load the requesting creator's stats once into the serializer context as a `dict[str, int]`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(campaigns): creator campaign discovery and detail (FR-11, FR-12)"`

---

# Phase 6: Proposals, FR-13 to FR-16 (Track D)

### Task 17: Proposal model, submission, withdrawal, apply state (FR-13, FR-12 apply state)

**Files:**
- Create: `apps/proposals/{models,serializers,services,views,urls}.py`, `apps/proposals/tests/{factories,test_submit,test_withdraw}.py`
- Modify: `apps/campaigns/serializers.py` (detail gets `accepted_count`, `all_creators_selected`, `can_apply`, `apply_blocked_reason`), `config/urls.py`

**Interfaces:**
- Consumes: `Campaign`, `CampaignFactory` (Task 15), `notify` (Task 10), `validate_safe_url`.
- Produces:
  - `Status(TextChoices)`: `PENDING`, `SHORTLISTED`, `ACCEPTED`, `REJECTED`, `WITHDRAWN`; `ACTIVE_STATUSES = (PENDING, SHORTLISTED, ACCEPTED)`.
  - `Proposal(campaign FK, creator FK User, status, cover_message, proposed_rate Decimal, portfolio_links JSON list (≤ 3 valid URLs), experience_note, withdrawal_reason(300) blank, created_at, updated_at)` with `UniqueConstraint(fields=["campaign","creator"], condition=Q(status__in=ACTIVE_STATUSES), name="uniq_active_proposal_per_creator_campaign")`. `ProposalFactory`.
  - `submit_proposal(*, creator: User, campaign_id: int, cover_message: str, proposed_rate: Decimal, portfolio_links: list[str], experience_note: str) -> Proposal`: locks the campaign row; requires `status=="published"` **and** `deadline > now()` **(RF1)**; blocks when an active or Rejected proposal exists; notifies the brand (`PROPOSAL_RECEIVED`). Errors (all `Conflict`/409): `campaign_closed`, `proposal_exists`, `proposal_rejected`.
  - `withdraw_proposal(*, creator: User, proposal_id: int, reason: str | None) -> Proposal`: allowed from Pending, Shortlisted, Accepted; reason required (1–300 chars) only when Accepted; blocks Rejected and already Withdrawn (`invalid_transition`); notifies the brand (`PROPOSAL_WITHDRAWN`, payload `slot_opened=True` when it was Accepted).
  - `POST campaigns/{id}/proposals/` → 201; `POST creators/me/proposals/{id}/withdraw/` → 200. There is no edit endpoint (PUT/PATCH → 405).
  - Campaign detail: `accepted_count` = currently Accepted; `all_creators_selected = accepted_count == creators_needed`; `can_apply` is false with `apply_blocked_reason` ∈ {`active_proposal`, `proposal_rejected`, `campaign_closed`} otherwise true.

- [ ] **Step 1: Write the failing tests:** `test_submit_creates_pending_and_notifies_brand`; `test_second_active_proposal_409`; `test_submit_after_rejection_409` **(RF4)**; `test_resubmit_after_withdrawal_on_published_campaign_ok_creates_new_row`; `test_resubmit_after_withdrawal_on_closed_campaign_409` **(RF4)**; `test_submit_to_closed_campaign_409`; `test_submit_after_deadline_before_autoclose_409` **(RF1)**; `test_submit_to_draft_campaign_404`; `test_more_than_3_links_rejected`; `test_javascript_link_rejected_and_html_stripped_from_message` **(RF2)**; `test_two_simultaneous_submits_create_one_active_proposal_and_one_409` **(RF4)** (transactional test, 2 threads, asserts no 500); `test_proposal_cannot_be_edited_405`; `test_withdraw_pending_and_shortlisted_without_reason`; `test_withdraw_accepted_requires_reason_max_300`; `test_withdraw_rejected_409`; `test_withdraw_accepted_notifies_brand_slot_opened`; `test_withdraw_after_campaign_closed_allowed`; `test_cannot_withdraw_other_creators_proposal_404` **(RF3)**; `test_campaign_detail_apply_state_matrix` (no proposal → can_apply; Pending → blocked `active_proposal`; Rejected → `proposal_rejected`; Withdrawn+Published → can_apply again; closed → `campaign_closed`); `test_all_creators_selected_flag`.
- [ ] **Step 2: Run** `pytest apps/proposals -v` → FAIL.
- [ ] **Step 3: Implement.** Catch `IntegrityError` from the partial unique constraint and raise `proposal_exists`.
- [ ] **Step 4: Run** `pytest apps/proposals apps/campaigns -v` → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(proposals): submission, withdrawal and apply state (FR-13)"`

### Task 18: Brand proposal list (FR-14)

**Files:**
- Create: `apps/proposals/tests/test_brand_list.py`
- Modify: `apps/proposals/{serializers,views,urls}.py`

**Interfaces:**
- Consumes: `annotate_primary_stats` (Task 8), `Proposal` (Task 17).
- Produces: `GET brand/campaigns/{id}/proposals/` (brand owner only; paginated; newest first). Query `status` ∈ {pending, shortlisted, accepted, rejected, withdrawn}; **Withdrawn excluded unless** `status=withdrawn`. Response wraps `{"accepted_count": int, "creators_needed": int, "results": [...]}` (count includes only currently Accepted). Each item: proposal id, creator `{id, name, niche, platform, followers, engagement_rate, is_verified}`, proposed rate, cover message, portfolio links, experience note, status, `withdrawal_reason` (only when set), `profile_url` (`creators/{id}/`).

- [ ] **Step 1: Write the failing tests:** `test_list_newest_first`; `test_withdrawn_hidden_by_default_and_shown_with_filter`; `test_status_filter`; `test_accepted_count_counts_only_currently_accepted` (an Accepted-then-withdrawn proposal not counted); `test_withdrawal_reason_visible_for_accepted_then_withdrawn`; `test_item_contains_creator_stats_and_profile_link`; `test_other_brands_campaign_proposals_404` **(RF3)**; `test_creator_role_403`; `test_query_count_constant_for_50_proposals` (`django_assert_max_num_queries(7)`).
- [ ] **Step 2: Run** `pytest apps/proposals/tests/test_brand_list.py -v` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(proposals): brand proposal list (FR-14)"`

### Task 19: Shortlist / Accept / Reject with race-safe capacity (FR-15)

**Files:**
- Create: `apps/proposals/tests/{test_status_actions,test_accept_concurrency}.py`
- Modify: `apps/proposals/{services,views,urls}.py`

**Interfaces:**
- Consumes: `Proposal`, `Status` (Task 17), `notify` (Task 10).
- Produces:
  - `shortlist_proposal(*, brand: User, proposal_id: int) -> Proposal`, `accept_proposal(*, brand: User, proposal_id: int) -> Proposal`, `reject_proposal(*, brand: User, proposal_id: int) -> Proposal`.
  - Errors: `CampaignFull(Conflict)` code `campaign_full`, message exactly "All creators for this campaign have already been selected."; `InvalidTransition(Conflict)` code `invalid_transition`.
  - `accept_proposal` flow inside `transaction.atomic()`: (1) `Campaign.objects.select_for_update()` by the proposal's campaign (always lock the campaign first, then the proposal, to avoid deadlocks); (2) if the proposal is already Accepted return it unchanged with no error and no notification; (3) require Pending or Shortlisted else `InvalidTransition`; (4) if accepted count ≥ `creators_needed` raise `CampaignFull`; (5) set Accepted; (6) notify the creator via `transaction.on_commit`.
  - Rules: Shortlisted → only Accept/Reject; Pending → any; Accepted/Rejected/Withdrawn cannot be shortlisted or rejected (`invalid_transition`); Shortlist on Shortlisted → 409 (Decision 10). All actions work after the campaign closes.
  - `POST brand/proposals/{id}/shortlist/|accept/|reject/` (brand owner of the campaign; others 404).

- [ ] **Step 1: Write the failing tests:** `test_pending_can_be_shortlisted_accepted_rejected`; `test_shortlisted_can_be_accepted_or_rejected_but_not_reshortlisted`; `test_accepted_cannot_be_rejected_and_rejected_cannot_be_accepted`; `test_withdrawn_cannot_be_acted_on`; `test_each_action_notifies_creator`; `test_actions_work_after_campaign_closed`; `test_accept_blocked_when_full_with_exact_message` (and shortlist/reject still succeed on other proposals); `test_withdraw_frees_slot_and_accept_works_again_even_after_close`; `test_double_accept_is_idempotent_count_plus_one_no_error_one_notification`; `test_two_simultaneous_accepts_on_last_slot_exactly_one_succeeds` (`@pytest.mark.django_db(transaction=True)`, `ThreadPoolExecutor(2)`, assert one 200 and one 409 `campaign_full`, `Proposal.objects.filter(status="accepted").count() == 1`); `test_twenty_concurrent_accepts_with_creators_needed_3_yield_exactly_3`; `test_other_brands_proposal_404` **(RF3)**; `test_creator_role_403`.
- [ ] **Step 2: Run** `pytest apps/proposals/tests/test_status_actions.py apps/proposals/tests/test_accept_concurrency.py -v` → FAIL.
- [ ] **Step 3: Implement** per the flow above. Each view calls exactly one service function and maps domain errors via the envelope.
- [ ] **Step 4: Run** → PASS. Run the concurrency file 10 times (`pytest apps/proposals/tests/test_accept_concurrency.py --count=10`, using `pytest-repeat`) to confirm it is stable.
- [ ] **Step 5: Commit** `git commit -m "feat(proposals): shortlist/accept/reject with row-locked capacity (FR-15)"`

### Task 20: Creator application tracking (FR-16)

**Files:**
- Create: `apps/proposals/tests/test_my_proposals.py`
- Modify: `apps/proposals/{serializers,views,urls}.py`

**Interfaces:**
- Produces: `GET creators/me/proposals/` (creator-only; paginated; newest first; filter `status`). Item: proposal id, status, proposed rate, created_at, withdrawal_reason, and campaign `{id, title, status, brand: {id, name}}`. Withdrawn proposals stay in the list; a resubmission is a separate entry. Status only; no messaging fields.

- [ ] **Step 1: Write the failing tests:** `test_lists_all_statuses_including_withdrawn`; `test_resubmission_appears_as_new_entry_alongside_withdrawn_one`; `test_only_own_proposals_visible` **(RF3)**; `test_status_filter`; `test_brand_role_403`; `test_closed_campaign_still_shown`.
- [ ] **Step 2: Run** `pytest apps/proposals/tests/test_my_proposals.py -v` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(proposals): creator application tracking (FR-16)"`

---

# Phase 7: Dashboards, FR-17, FR-18 (Track D)

### Task 21: Creator dashboard (FR-17)

**Files:**
- Create: `apps/dashboards/{services,views,urls}.py`, `apps/dashboards/tests/test_creator_dashboard.py`
- Modify: `config/urls.py`

**Interfaces:**
- Consumes: `completion_percent` (Task 7), `YouTubeConnection` (Task 11), published-campaign queryset (Task 16), `Proposal` (Task 17).
- Produces: `creator_dashboard(user: User) -> dict` and `GET creators/me/dashboard/` returning `profile_completion` (int), `youtube` (`{connected, status, last_synced_at, needs_reconnect}`), `available_campaigns` (latest 5 Published, deadline in the future, newest first, with `eligible`), `applications` (latest 10 with statuses), `accepted_campaigns` (proposals currently Accepted), `performance` (`{proposals_sent, accepted, acceptance_rate: float | None}`). `proposals_sent` counts every proposal ever submitted including Withdrawn; `accepted` counts only currently Accepted; `acceptance_rate = accepted / proposals_sent`, or `None` when 0 sent (Decision 8).

- [ ] **Step 1: Write the failing tests:** `test_new_creator_dashboard_has_zero_state_and_null_rate`; `test_available_campaigns_limited_to_5_published_future_newest_first`; `test_performance_withdrawn_counts_as_sent`; `test_accepted_then_withdrawn_not_counted_as_accepted` (sent 2, one Accepted, one Accepted→Withdrawn → rate 0.5); `test_accepted_campaigns_listed_separately`; `test_reconnect_prompt_when_needs_reconnect`; `test_brand_role_403`; `test_dashboard_query_count_bounded` (`django_assert_max_num_queries(12)`).
- [ ] **Step 2: Run** `pytest apps/dashboards/tests/test_creator_dashboard.py -v` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(dashboards): creator dashboard (FR-17)"`

### Task 22: Brand dashboard (FR-18)

**Files:**
- Create: `apps/dashboards/tests/test_brand_dashboard.py`
- Modify: `apps/dashboards/{services,views,urls}.py`

**Interfaces:**
- Produces: `brand_dashboard(user: User) -> dict` and `GET brands/me/dashboard/` returning `total_campaigns`, `active_campaigns` (Published), `total_proposals` (all statuses incl. Withdrawn), `shortlisted_count`, `accepted_count` (currently in that status only), `campaigns` (each `{id, title, status, proposals_url, proposal_count, accepted_count, creators_needed}`). Aggregated with conditional `Count(filter=...)`, not per-campaign queries.

- [ ] **Step 1: Write the failing tests:** `test_empty_brand_dashboard_all_zero`; `test_total_proposals_includes_withdrawn`; `test_shortlisted_and_accepted_count_only_current_status`; `test_active_campaigns_counts_only_published`; `test_campaign_rows_link_to_proposal_list`; `test_other_brands_data_excluded` **(RF3)**; `test_creator_role_403`; `test_query_count_constant_for_20_campaigns` (`django_assert_max_num_queries(6)`).
- [ ] **Step 2: Run** `pytest apps/dashboards/tests/test_brand_dashboard.py -v` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest -v` (whole suite) → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(dashboards): brand dashboard (FR-18)"`

> **Milestone: core complete.** Merge Phases 0–7 and demo with the frontend before starting Phase 8.

---

# Phase 8: Hardening & Delivery (all tracks)

### Task 23: Security sweep (Section 4.2)

**Files:**
- Create: `apps/core/tests/test_security_matrix.py`
- Modify: `config/settings/{base,prod}.py`

**Interfaces:**
- Produces: `PUBLIC_ROUTES: set[str]` (in the test file): `api/v1/health/`, `auth/register/`, `auth/login/`, `auth/password-reset/request/`, `auth/password-reset/confirm/`, `social/youtube/callback/`, `/api/schema/`, `/api/docs/`. Prod settings: `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, secure cookies, `ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` from env (no wildcard).

- [ ] **Step 1: Write the failing tests:** `test_every_route_requires_auth_except_public_list` (walk `get_resolver()` URL patterns, call each with no token, assert 401 unless in `PUBLIC_ROUTES`); `test_role_matrix` (for every non-public route, the wrong role gets 403 and never 200); `test_no_secret_fields_in_any_serializer_output` (`access_token`, `refresh_token`, `password`, `code_hash` absent from sample responses); `test_throttles_exist_for_login_register_and_reset`; `test_error_responses_never_leak_stack_traces` (`DEBUG=False`); `test_cors_rejects_unlisted_origin`.
- [ ] **Step 2: Run** `pytest apps/core/tests/test_security_matrix.py -v` → FAIL where gaps exist.
- [ ] **Step 3: Fix** every gap the matrix finds (permissions, throttles, settings).
- [ ] **Step 4: Run** `pytest -v` and `python manage.py check --deploy --settings=config.settings.prod` (env vars set) → PASS, zero deploy warnings.
- [ ] **Step 5: Commit** `git commit -m "chore(security): auth matrix, prod hardening"`

### Task 24: Performance, indexes and demo data (Section 4.1)

**Files:**
- Create: `apps/core/management/commands/seed_demo.py`, `apps/core/tests/test_seed_demo.py`
- Modify: model `Meta.indexes` in `profiles`, `campaigns`, `proposals`

**Interfaces:**
- Produces: `python manage.py seed_demo [--creators 200 --brands 20 --campaigns 100]` creates deterministic demo users (documented password in the README and `.env.example` demo section, non-production only), profiles, stats (mix of verified and unverified), campaigns in all statuses, and proposals in all statuses. Refuses to run when `DEBUG=False`. Indexes: `Campaign(status, deadline)`, `Campaign(brand, status)`, `Proposal(campaign, status, -created_at)`, `Proposal(creator, -created_at)`, `PlatformStats(creator, platform)` (exists via the unique constraint).

- [ ] **Step 1: Write the failing tests:** `test_seed_demo_creates_requested_counts_and_is_idempotent`; `test_seed_demo_refuses_when_debug_false`; `test_directory_and_campaign_list_are_fast_with_seeded_data` (seed 200 creators / 100 campaigns; each list endpoint responds in < 1 s on the test machine and within the query budgets already asserted in Tasks 14, 16, 18).
- [ ] **Step 2: Run** `pytest apps/core/tests/test_seed_demo.py -v` → FAIL.
- [ ] **Step 3: Implement** command and indexes; check slow queries with `EXPLAIN ANALYZE` on the three list endpoints and note findings in the PR.
- [ ] **Step 4: Run** `pytest -v` → PASS.
- [ ] **Step 5: Commit** `git commit -m "perf: indexes and demo seed data"`

### Task 25: API docs, README, Docker, deployment config (Section 4.6)

**Files:**
- Create: `Dockerfile`, `docs/DEPLOYMENT.md`, `apps/core/tests/test_schema.py`
- Modify: `README.md`, `.env.example`, `apps/**/views.py` (add `extend_schema` tags/examples where the generated schema is ambiguous)

**Interfaces:**
- Produces: a Swagger UI at `/api/docs/` with endpoints grouped by tag (Auth, Profiles, Social, Campaigns, Proposals, Notifications, Dashboards); a `schema.yml` export the frontend can import into Postman; a README with setup, env var table, how to run web + worker + beat, how to register the Google OAuth app (consent screen in Testing mode, test users, redirect URI), how to run tests, and the 7-day Google refresh-token expiry note.

- [ ] **Step 1: Write the failing test** `test_schema_generation_has_no_warnings`: runs `call_command("spectacular", "--validate", "--fail-on-warn")`.
- [ ] **Step 2: Run** `pytest apps/core/tests/test_schema.py -v` → FAIL (undocumented serializers / ambiguous types).
- [ ] **Step 3: Fix** warnings with explicit serializers and `extend_schema`; write the docs; build the image: `docker build -t micro-influencers-api .` and start `web`, `worker`, `beat` from it with docker compose.
- [ ] **Step 4: Run** `pytest -v` and `docker build` → PASS / success; follow the README from a clean clone on another machine and confirm `GET /api/v1/health/` works.
- [ ] **Step 5: Commit** `git commit -m "docs: swagger tags, readme, dockerfile, deployment notes"`

---

# Phase 9: Extensions (build only if Phases 0–8 are merged and stable; cut from the bottom)

Order is fixed by PRD §2.2: Task 26 → Tasks 27–28 → Task 29 → Task 30. Last two days before the deadline are bug fixes only.

### Task 26: Email notifications and email verification (FR-24)

**Files:**
- Create: `apps/notifications/{emails,tests/test_email_notifications}.py`, `apps/accounts/tests/test_email_verification.py`, `apps/core/templates/email/{notification,verify_email}.txt`
- Modify: `apps/accounts/{models,services,views,urls}.py` (`User.email_verified: bool`, `User.email_notifications_enabled: bool = True`), `apps/notifications/services.py`, `apps/core/emailing.py`, `apps/accounts/services.py` (`register_user` queues a verification code)

**Interfaces:**
- Consumes: `OneTimeCode` with `purpose="email_verification"` and `issue_code`/`verify_code` (Task 6), `queue_email` (Task 5), `notify` (Task 10).
- Produces:
  - `POST auth/email/verify/ {code}` (authenticated; same 10 min / single-use / 5 attempts rules); `POST auth/email/resend/` (60 s cooldown, code `resend_cooldown` 429, rate limited); `GET, PATCH settings/notifications/ {email_enabled: bool}`.
  - `notify()` additionally enqueues, via `transaction.on_commit`, an email **only if** `user.is_active and user.email_verified and user.email_notifications_enabled`. Body contains the event name, one short sentence and one button URL (`FRONTEND_URL` + app path); no rates, proposal text or stats; footer links to notification settings. Reset and verification codes ignore the toggle.
  - `deliver_email` becomes `autoretry_for=(Exception,)`, `retry_backoff=True`, `max_retries=5`; failures logged; never affects the in-app notification.

- [ ] **Step 1: Write the failing tests:** the three acceptance criteria (`test_accepted_with_toggle_on_and_verified_email_sends_in_app_and_email`, `test_toggle_off_or_unverified_sends_in_app_only`, `test_provider_down_keeps_in_app_and_retries_without_user_error`); `test_verification_code_sent_after_registration`; `test_unverified_user_can_still_log_in`; `test_verify_marks_email_verified`; `test_resend_within_60s_rejected`; `test_email_body_contains_no_rate_or_message_text`; `test_reconnect_email_sent_once_per_token_failure`; `test_suspended_user_gets_no_email`; `test_reset_code_sent_even_when_notifications_off`.
- [ ] **Step 2: Run** `pytest apps/notifications apps/accounts -v` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest -v` → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(notifications): email notifications and verification (FR-24)"`

### Task 27: Collaboration completion and deliverables (FR-20)

**Files:**
- Create: `apps/proposals/{deliverables}.py`, `apps/proposals/tests/test_deliverables.py`
- Modify: `apps/proposals/{models,serializers,views,urls}.py` (`Proposal.completed_at: DateTime | None`)

**Interfaces:**
- Produces: `Deliverable(proposal FK, post_url, platform, note, updated_at)`; `GET, POST creators/me/proposals/{id}/deliverables/`; `PATCH, DELETE creators/me/proposals/{id}/deliverables/{did}/`; `GET brand/campaigns/{id}/deliverables/` (grouped by proposal); `POST brand/proposals/{id}/complete/`. Services `submit_deliverable(*, creator: User, proposal_id: int, post_url: str, platform: str, note: str = "") -> Deliverable` and `complete_proposal(*, brand: User, proposal_id: int) -> Proposal`.

- [ ] **Step 1: Write the failing tests:** `test_deliverables_only_on_accepted_proposals`; `test_creator_can_update_until_completion_then_locked`; `test_only_accepted_can_be_completed_final_and_per_creator` (one of two accepted completed, other not); `test_completed_proposal_cannot_be_withdrawn_409` (Decision 12); `test_brand_views_deliverables_of_own_campaign_only` **(RF3)**; `test_javascript_post_url_rejected` **(RF2)**.
- [ ] **Step 2: Run** `pytest apps/proposals/tests/test_deliverables.py -v` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest -v` → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(proposals): deliverables and completion (FR-20)"`

### Task 28: Creator ratings and reviews (FR-21)

**Files:**
- Create: `apps/reviews/{models,services,serializers,views,urls}.py`, `apps/reviews/tests/test_reviews.py`
- Modify: `apps/profiles/{models,directory_views,filters}.py` (`CreatorProfile.rating_avg: Decimal | None`, `rating_count: int`; directory gets `min_rating` filter and `ordering=rating`)

**Interfaces:**
- Produces: `Review(proposal OneToOne, brand FK User, creator FK User, rating 1–5, text ≤ 500, created_at)`; `create_review(*, brand: User, proposal_id: int, rating: int, text: str = "") -> Review` (completed proposals only, owning brand only, one per proposal, no edits); `recalculate_rating(creator_id: int) -> None` (also called by Task 29); `POST brand/proposals/{id}/review/`; `GET creators/{id}/reviews/`. Average and count surface on the creator profile, directory cards and proposal items.

- [ ] **Step 1: Write the failing tests:** `test_review_requires_completed_collaboration`; `test_only_owning_brand_can_review` **(RF3)**; `test_second_review_for_same_proposal_409`; `test_rating_out_of_range_rejected`; `test_text_over_500_rejected`; `test_average_and_count_recalculated`; `test_min_rating_filter_and_rating_sort`; `test_review_cannot_be_edited_405`.
- [ ] **Step 2: Run** `pytest apps/reviews -v` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest -v` → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(reviews): creator ratings and reviews (FR-21)"`

### Task 29: Admin panel API (FR-22)

**Files:**
- Create: `apps/adminpanel/{models,services,serializers,views,urls}.py`, `apps/adminpanel/tests/test_admin.py`, `apps/accounts/management/commands/create_admin.py`

**Interfaces:**
- Consumes: `IsAdminRole` (Task 2), `recalculate_rating` (Task 28), `close_campaign` (Task 15).
- Produces: `AdminActionLog(admin FK, action, target_type, target_id, reason, created_at)`; `python manage.py create_admin --email --username` (password prompted, never an argument); `POST admin/auth/login/` (admin role only, separate from public login); `GET admin/users/` (search, filter by role/status), `POST admin/users/{id}/suspend/|reactivate/`, `DELETE admin/users/{id}/`; `POST admin/campaigns/{id}/close/`; `DELETE admin/reviews/{id}/`; `GET admin/overview/`. Every mutating action requires `reason` and writes a log row. Suspended users (`is_active=False`) cannot log in and their existing tokens stop working.

- [ ] **Step 1: Write the failing tests:** `test_public_registration_cannot_create_admin`; `test_non_admin_gets_403_on_every_admin_route`; `test_admin_cannot_suspend_or_delete_self`; `test_suspended_user_cannot_login_and_token_rejected`; `test_reactivate_restores_login`; `test_every_action_requires_reason_and_logs_admin_target_reason_timestamp`; `test_removing_review_recalculates_rating`; `test_admin_close_campaign`; `test_overview_counts_users_campaigns_by_status_proposals_and_signups_over_time`; `test_delete_requires_reason`.
- [ ] **Step 2: Run** `pytest apps/adminpanel -v` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest -v` → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(admin): user management, moderation, overview (FR-22)"`

### Task 30: Campaign performance analytics (FR-23), proposal metrics first

**Files:**
- Create: `apps/campaigns/analytics.py`, `apps/campaigns/tests/test_analytics.py`
- Modify: `apps/campaigns/{models,views,urls}.py` (`CampaignView(campaign FK, creator FK User, view_count int, last_viewed_at)` unique on `(campaign, creator)`; creator campaign detail increments it)

**Interfaces:**
- Produces: `campaign_metrics(campaign: Campaign) -> dict` and `GET brand/campaigns/{id}/analytics/` (owner only) returning `views` (sum of `view_count`), `funnel` (`received`, `shortlisted`, `accepted`, `rejected`, `withdrawn`, by current status; `received` includes Withdrawn), `accepted_vs_needed`, `avg_proposed_rate`, `budget_per_creator`, `acceptance_rate` (`accepted ÷ received`, `None` when 0 received, Accepted-then-withdrawn not counted).
- **Content performance (cut first):** `deliverable_performance(campaign: Campaign) -> list[dict]` uses the video id parsed from each YouTube deliverable URL (Task 27) and `videos.list` with the server API key; returns `{views, likes, comments, engagement_rate}` per deliverable, or `"not_available"` per field when the platform is not YouTube or the API fails. Build this subpart only if time remains.

- [ ] **Step 1: Write the failing tests:** `test_funnel_counts_by_current_status`; `test_acceptance_rate_excludes_accepted_then_withdrawn_and_is_null_with_no_proposals`; `test_avg_rate_versus_budget`; `test_repeat_views_by_same_creator_increment_view_count_not_rows`; `test_other_brands_analytics_404` **(RF3)**; `test_deliverable_performance_returns_not_available_for_non_youtube_or_api_failure` (subpart).
- [ ] **Step 2: Run** `pytest apps/campaigns/tests/test_analytics.py -v` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest -v` → PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(campaigns): campaign analytics (FR-23)"`

---

## Self-Review Record

**Spec coverage:** FR-01 → T3; FR-02 → T4, T5, T6; FR-03 → T7, T8; FR-04 → T7; FR-05 → T8, T11–T13; FR-06 → T9; FR-07/08 → T14; FR-09/10 → T15; FR-11/12 → T16, T17; FR-13 → T17; FR-14 → T18; FR-15 → T19; FR-16 → T20; FR-17 → T21; FR-18 → T22; FR-19 → T10 (events fired in T13, T15, T17, T19); FR-20 → T27; FR-21 → T28; FR-22 → T29; FR-23 → T30; FR-24 → T26. NFR 4.1 → T14/16/18/24; 4.2 → T2, T3, T4, T6, T11, T12, T23; 4.3 → T13, T15, T19; 4.4 → T12 (consent, disconnect) and Decision 11; 4.5 → `null` photo contract (T7) and envelope errors (T2); 4.6 → T1, T25. Section 4.4's Privacy Policy and Terms pages are frontend work.

**Known risks to watch:** The Google OAuth app must be registered in Testing mode with real test users before Task 12 can be demoed end to end; do this today. The email provider's sender domain (SPF/DKIM) must be live before Task 6 can be tested against real Gmail and Outlook inboxes (PRD §5).
