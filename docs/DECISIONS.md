# Decisions log

Choices made while building the backend where the PRD was silent, ambiguous or needed a trade-off.
Each entry says what was decided, why, and what it costs if it turns out to be wrong. They are listed
in the order they were made, grouped by build phase. Change any of them deliberately: most are one
line of code, and the tests that pin them sit next to the code.

## Phase 0: Foundation

- Python 3.13.5 + Django 5.2 instead of plan's 3.12 — only interpreter installed; Django 5.2 supports 3.13 — cost if wrong: pin a 3.12 interpreter later.
- no Docker/PostgreSQL on this machine; verification uses pixeltable-pgserver (embedded PostgreSQL 18, pip, inside git-ignored .venv) via DATABASE_URL — repo still ships docker-compose with postgres:16 per plan — cost if wrong: minor PG16 vs 18 behavioural drift; real row-lock tests still run on real PostgreSQL.
- **Task 1** — DRF default auth class is stock simplejwt JWTAuthentication (not yet VersionedJWTAuthentication) — plan's 401 test needs an auth class with a WWW-Authenticate header; Task 4 swaps in the versioned class — cost if wrong: one setting line.
- **Task 1** — dropped django.contrib.admin/sessions/messages from INSTALLED_APPS (API-only; FR-22 admin is a DRF API, not Django admin) — cost if wrong: add apps back + migrations.
- **Task 2** — core.permissions compares role against literal strings 'creator'/'brand'/'admin' (accounts.Role arrives in Task 3 with identical values) — avoids core→accounts import cycle — cost if wrong: swap constants for Role members.

## Phase 1: Authentication

- T3 password-hash test asserts check_password/not-plaintext and that config.settings.base leaves PASSWORD_HASHERS at Django default (PBKDF2) instead of 'starts with pbkdf2_' — test settings deliberately use MD5 for speed — cost if wrong: none (prod hasher still verified by settings assertion).
- usernames also get a unique Lower(username) constraint + case-insensitive serializer check (PRD says unique; prevents 'Bob'/'bob' impersonation) — cost if wrong: drop constraint.
- **Task 5** — deliver_email Celery task lives in apps/core/tasks.py (not emailing.py) — Celery autodiscovery only imports tasks.py, otherwise a worker would silently not register it (test_deliver_email_task_is_registered_with_celery pins this); queue_email in emailing.py as planned — cost if wrong: none.
- **Task 6** — verify_code raises AFTER its transaction commits (attempt counter must persist on a wrong guess) and confirm_password_reset validates the new password in the serializer BEFORE consuming the code — a weak password must not burn the one-time code — cost if wrong: none.
- **Task 6** — inactive (suspended) users get no reset email, same generic response — avoids mailing suspended accounts (FR-22) — cost if wrong: one filter.

## Phase 2: Profiles and stats

- completion_percent is a list of 8 named checks over a fixed denominator of 8, integer half-up ((100*done+4)//8); T7 implements the 6 profile-field checks (max 75), T8 adds the primary-platform-stats check, T9 the portfolio check — so 'everything -> 100' is asserted in T9 — cost if wrong: none.
- profile rows are created by a post_save signal on User (profiles app, by role) instead of lazily on first access; get_or_create_profile kept as a safe accessor for users created before the signal existed — GETs never write, accounts does not import profiles — cost if wrong: an extra row per user.
- the {id} in creators/{id}/ and brands/{id}/ is the owning User's id — one public id per account and no profile-row dependency — cost if wrong: a rename in URLs/serializers.

## Phase 4: YouTube integration

- execute Task 13 BEFORE Task 12 (11 -> 13 -> 12). T13 depends only on T11/T10/T8, not on T12's endpoints; the one T13 test that needs the connect flow (reconnect after revocation restores 'connected') moves to T12. Also keeps the callback fast: it stores tokens and enqueues the first sync in the background (PRD 4.1: third-party calls never block page loads) — cost if wrong: none; task numbering in ledger stays plan-faithful.
- YouTubeClient gets one extra exception ChannelNotFound (a Google account with no YouTube channel) beyond the plan's three; exchange_code maps invalid_grant to TokenRevoked; 403 insufficientPermissions maps to TokenRevoked (scope withdrawn => reconnect) — cost if wrong: a mapping line.
- tests use a hand-written FakeYouTubeClient (apps/social/tests/fakes.py) patched at apps.social.services.get_youtube_client; HTTP-level behaviour of the real client is tested with the 'responses' library in T11 — cost if wrong: none.

## Phase 5: Campaigns and discovery

- directory rate filter matches a creator when at least one of their three rates lies inside [min_rate, max_rate]; sort-by-rate uses the cheapest non-null rate (Postgres LEAST ignores NULLs); creators with no value sort last in both directions — cost if wrong: a filter/ordering expression.
- default directory ordering is followers descending (nulls last) — PRD names sort keys but no default — cost if wrong: one default.
- query-string filters are validated by a serializer; invalid values (e.g. min_followers=abc, ordering=bogus) return 400 with per-field details rather than being ignored — cost if wrong: none.
- **Task 15** — serializer also rejects a past deadline on create/PATCH (plan only checks at publish) — early feedback, publish re-checks because time passes — cost if wrong: one validator.
- **Task 15** — PATCH/DELETE on a non-draft reports 409 campaign_not_editable BEFORE field validation — a frozen campaign is the more useful error — cost if wrong: none.

## Phase 6: Proposals

- annotate_primary_stats gains keyword args (creator_field='user_id', platform_field='primary_platform') so T18 reuses the single definition via creator_id / creator__creator_profile__primary_platform; defaults keep T14 unchanged — cost if wrong: none.
- withdraw_proposal locks campaign then proposal (same order as accept) — prevents deadlock — cost if wrong: none.
- T19 notifications are created inside the transaction (not on_commit) — atomic with the status change — cost if wrong: if a future caller wraps the action in an outer transaction that rolls back, the notification rolls back too (desired).
- can_apply reasons are prioritised active_proposal > proposal_rejected > campaign_closed (tell the creator what they did before telling them the campaign closed) — cost if wrong: one ordering.
- brand proposal item returns withdrawal_reason as null when the creator gave none (stable shape) rather than omitting the key — cost if wrong: none.
- **Task 19** — shortlist and reject also take the campaign-then-proposal lock (not only accept) — one lock order everywhere, no deadlock with withdraw — cost if wrong: slightly more contention per campaign.

## Phase 7: Dashboards

- available_campaigns is literally the 5 newest open campaigns (no exclusion of ones already applied to) — PRD gives no exclusion and applications are shown separately — cost if wrong: one NOT-IN filter.
- acceptance_rate is a ratio 0-1 rounded to 4 places (0.5 = 50%), null when nothing was sent — cost if wrong: frontend multiplies by 100.
- the brand dashboard lists the 50 newest campaigns (totals still cover all) and proposal_count per campaign includes withdrawn, matching the dashboard total — bounded response; cost if wrong: raise/page the cap.

## Phase 8: Hardening and delivery

- set NUM_PROXIES from env (default 0 = ignore X-Forwarded-For; prod default 1 = one reverse proxy) — cost if wrong: throttling keyed on the proxy IP if prod runs with the wrong proxy count; documented in DEPLOYMENT.md.
- add JSON handler404/handler500 using the standard error envelope — cost if wrong: remove two handlers.
- add CsrfViewMiddleware and XFrameOptionsMiddleware (inert for bearer-token DRF views, which are csrf_exempt) so check --deploy is clean without silencing checks — cost if wrong: none.
- **Task 24** — seed_demo is a thin command over apps/core/demo_data.seed() (bulk_create, per-index RNG, top-up semantics, demo password DemoPass123! documented) — each demo user depends only on its own index so reruns/top-ups are stable; profile rows created explicitly because bulk_create skips the post_save signal — cost if wrong: none. Task 24: fix: demo mobile numbers use crc32 not hash() (str hash is per-process random) — pinned by a literal-value test run under two PYTHONHASHSEEDs.
- **Task 25** — docs/openapi.yml is committed AND guarded by a drift test (fails with the regenerate command when stale); env-var drift tests tie settings -> .env.example -> README table; the existing 'schema validates' test moved from test_docs.py into test_schema.py — cost if wrong: contributors must regenerate openapi.yml after endpoint changes.
- **Task 25** — compose services web/worker/beat run the prod image/settings; local smoke runs use DJANGO_SETTINGS_MODULE=config.settings.dev (documented) because prod rightly rejects http:// CORS origins — cost if wrong: docs only.

## Phase 9: Extensions

- verify_code raises purpose-specific error classes — reset keeps invalid_reset_code/reset_code_*; email verification gets invalid_verification_code/verification_code_{expired,used,locked} — T6's contract is unchanged — cost if wrong: a dict of class names.
- deliver_email retries 5 times with exponential backoff and only on the final failure logs 'Failed to send email' and swallows it (T5 behaviour preserved: never raised to callers) — cost if wrong: none.
- notification emails use a fixed one-sentence body per event (no names, titles, rates or stats) plus one button; the in-app message is not reused — satisfies PRD 'no rates, proposal text or stats' strictly — cost if wrong: a template string per kind.
- email button paths are constants in apps/notifications/emails.py (creator: /creator/applications, /settings/connections; brand: /brand/campaigns/{id}/proposals, /brand/campaigns/{id}; footer /settings/notifications) — frontend must match or tell us — cost if wrong: edit one dict.
- the public /auth/login/ treats admin accounts as invalid credentials and admin/auth/login/ accepts only admins (separate panel, smaller attack surface) — cost if wrong: one role check each.
- content performance (FR-23 subpart) is served from a cached snapshot on Deliverable (views/likes/comments + synced_at) refreshed by a daily Celery task using a server-side YOUTUBE_API_KEY; the request path never calls Google (PRD 4.1) — cost if wrong: numbers can be up to a day old.
- **Task 27** — marking a collaboration Completed does not require any deliverable to exist (PRD only says only Accepted can be completed) and repeating it is an idempotent 200, like a second Accept — cost if wrong: one check.
- **Task 27** — deliverables per proposal capped at 20 (409 deliverables_full) — PRD silent, prevents unbounded growth. Task 27: no new notifications for FR-20 (the FR-19 event list is closed and the PRD says extension notifications are added only when specified) — cost if wrong: add kinds later.
- **Task 28** — recalculate_rating locks the creator's profile row before aggregating, so simultaneous reviews cannot leave a stale average (8-thread test, 12 repeats green) — cost if wrong: none.
- **Task 28** — the reviews app owns a 'Reviews' OpenAPI tag; rating_avg/rating_count were added to the creator card, detail, own profile and the brand's proposal creator block, and the earlier exact-shape tests were updated to include them.
- **Task 29** — deleting a brand recalculates the ratings of every creator it had reviewed (its reviews cascade away) — found by reading the cascade, pinned by test_deleting_a_brand_recalculates_the_ratings_it_gave.
- **Task 29** — AdminActionLog keeps admin_label/target_label text and SET_NULLs the admin FK so the audit trail survives deleting either party; a no-op admin close of an already-closed campaign is not logged; DELETE actions take the reason in the JSON body. Task 29: create_admin has no --password option by design (prompted twice, min 8 chars).
- **Task 30** — campaign views are one counter row per (campaign, creator), incremented on the creator's campaign DETAIL request only (list browsing and the brand's own pages do not count); content performance reads a daily snapshot on Deliverable and the endpoint never calls Google; a failed YouTube batch keeps the previous numbers and is retried by the next daily run; engagement rate = (likes+comments)/views as a 2-decimal string, not_available unless all three counters are known and views>0; editing a deliverable link discards the old video's numbers; YOUTUBE_API_KEY is optional (absent -> not_available). Task 30: the content-performance subpart (cut-first per the PRD) WAS built because time remained.

## Review fixes: After the whole-repo code review (findings 1 to 10)

- finding 1 — production is the default for manage.py, wsgi and celery via one helper (config/bootstrap.py); local development opts in with DJANGO_SETTINGS_MODULE=config.settings.dev in .env (the example file has it); the real environment always beats .env; docker-compose forces prod for web/worker/beat because env_file values override the image ENV — cost if wrong: developers without a .env must export the variable; DOTENV_PATH exists only so tests can run without a .env.
- finding 2 — the HEALTHCHECK moved from the Dockerfile (shared by worker and beat) to the web service in docker-compose.yml; worker and beat have none; other hosts must attach the probe to the web container only — cost if wrong: no automatic liveness for the worker/beat (add a celery inspect ping later).
- finding 3 — network errors from Google now carry only the exception class name (raised 'from None' so the chained original with the URL is dropped), and urllib3 is pinned to WARNING in LOGGING; I did NOT move the API key to the X-Goog-Api-Key header because I cannot verify the YouTube Data API honours it without a real key — cost if wrong: the key still travels in the query string to Google (as before) but no longer reaches our logs.
- finding 4 — YouTube connect now finishes in a separate authenticated step (POST /social/youtube/complete/ {state, code}) so the state must have been issued to the logged-in creator; the callback only validates the state signature and redirects to FRONTEND_URL/settings/connections?youtube=confirm&code=..&state=..; the uid check runs BEFORE the one-time nonce is claimed so a wrong person cannot burn another's state; this CHANGES the frontend contract (the old ?youtube=success redirect is gone) — cost if wrong: one extra frontend call; chosen over a cookie because the API and SPA may be on different sites.
- finding 5 — notification emails are prepared inside a catch-all (never raises from on_commit) and a payload missing a link field falls back to the app home page with a warning — cost if wrong: a developer mistake produces a generic link instead of an error.
- finding 6 — a Redis outage no longer takes login, sign-up, password reset or email verification down: throttled views use FailOpenScopedRateThrottle, which lets the request through (and logs a warning) when the cache is unreachable; real configuration mistakes are still errors; cache sockets time out after 2 seconds so a dead Redis cannot hang requests; the YouTube connect flow answers 503 temporarily_unavailable (its one-time nonce needs the cache); background jobs are queued through enqueue(), so a broker outage is logged instead of failing a request whose data was already saved — cost if wrong: while Redis is down rate limits are not enforced (the per-code attempt limit lives in the database and stays on).
- finding 7 — HSTS is opt-in per deployment: SECURE_HSTS_SECONDS (default one year), SECURE_HSTS_INCLUDE_SUBDOMAINS and SECURE_HSTS_PRELOAD default off, and preload without include-subdomains is refused at start-up; the matching Django deployment-check warnings are silenced only while the option is off — cost if wrong: an operator who wants preload must set two variables.
- finding 8 — lock_proposal_for_brand lives in apps/proposals/locks.py (campaign row first, then proposal row) and is imported by proposals, deliverables and reviews; an AST test forbids importing another app's underscore-prefixed names — cost if wrong: none.
- finding 9 — the campaign view counter is one INSERT ... ON CONFLICT DO UPDATE statement (PostgreSQL), so there is one query and no race — cost if wrong: the counter now requires PostgreSQL (already required).
- finding 10 — the daily YouTube sync spreads connections evenly over YOUTUBE_SYNC_SPREAD_SECONDS (default 1800) using task countdowns, ordered by id — cost if wrong: a creator's stats can refresh up to 30 minutes after 03:00 UTC.

## Verification gates: a change from the PRD

- **Brands need a verified email to publish a campaign or accept a proposal.** `publish_campaign` and
  `accept_proposal` answer 403 `brand_email_unverified` otherwise. Saving, editing and deleting drafts,
  shortlisting and rejecting stay open.
- **Creators need a connected YouTube channel to apply.** `submit_proposal` answers 403
  `creator_youtube_required` unless the creator has YouTube stats with `is_verified = true`. Manual stats
  (any platform, including a hand-typed YouTube entry) do not count, and the channel works for campaigns on
  any platform. Disconnecting YouTube marks the stats Unverified, so it removes the right to apply. A creator's
  email verification does not replace this.
- **A creator also needs at least `MIN_CREATOR_FOLLOWERS` (default 1,000) YouTube subscribers.** `apply_snapshot`
  stores `is_verified = subscribers >= MIN_CREATOR_FOLLOWERS` every time the channel is read (when connecting, on the
  daily sync and on Refresh), so a channel that grows becomes Verified and one that shrinks stops being Verified. A
  connected channel below the minimum stays connected. `submit_proposal` checks the count again at apply time, so
  raising the minimum applies at once. A connected channel under the minimum gets 403 `creator_followers_too_low`
  with both numbers in the message; no YouTube at all still gets `creator_youtube_required`. `/social/youtube/` and the
  creator dashboard report `followers`, `minimum_followers` and `below_minimum`.
- **The direct-connect endpoints were removed** (`POST /social/youtube/direct-connect/`,
  `/social/direct-connect/{platform}/`, `GET /social/challenge/{platform}/`). They marked stats Verified from a handle
  and a follower count the caller typed, with no proof, which bypassed both the Google sign-in rule and the minimum.
  Migration `social.0004` takes the Verified flag from anything they (or a lower minimum) left behind: non-YouTube
  stats, channels linked by handle, and Verified channels under the minimum. Numbers are never changed.
- **A brand also needs one connected platform.** `publish_campaign` and `accept_proposal` check the email first
  (`brand_email_unverified`), then that the brand has at least one `BrandSocialAccount` (`brand_platform_required`).
  (Superseded: YouTube no longer counts for a brand, see the last verification entry below.) Instagram, TikTok and Facebook
  are a link the brand types, checked to be on that platform's website; nothing proves ownership (that needs Meta or
  TikTok approval), so they are stored with `is_verified = false` ("Added") but still count as connected. Existing
  email-verified brands must connect a platform before they can publish or accept again. Endpoints:
  `GET /brands/me/social/`, `PUT|DELETE /brands/me/social/{platform}/`. `/auth/me/` reports `platform_connected` for brands.
- **Brands and creators both confirm their email with a 6-digit code** sent after sign-up (`POST /auth/email/verify/`,
  `/auth/email/resend/`). For a creator this is a separate check from YouTube: it does not let them apply (only a
  connected YouTube channel does), and it makes them eligible for notification emails (FR-24).
- **Why this differs from the PRD:** FR-02, FR-10 and FR-24 say unverified users can use the platform and that
  unverified stats still count towards applying. The owner chose stricter rules to keep fake or throwaway
  accounts out of the marketplace.
- **Cost if wrong:** while Google keeps the app in Testing mode only registered test users can connect
  YouTube (and their tokens expire after 7 days), so most real creators cannot apply until the app is
  verified by Google. A brand also depends on email delivery working to verify.
- The checks live in `apps/accounts/verification.py`. `seed_demo` makes demo brands email-verified and gives
  every demo creator except each fifth one (`demo_creator_005`, `_010`, ...) a verified YouTube channel.

## Known gaps and things deliberately left alone

- **Suspended accounts keep their content.** Suspending blocks login and invalidates tokens (and stops
  emails), but a suspended brand's published campaigns stay visible and a suspended creator's proposals
  stay in brands' lists. The PRD only requires that suspended users cannot log in; an admin can close a
  campaign separately. Hiding their content would be a small follow-up.
- **No clean-up of old one-time codes and notifications.** Expired reset/verification codes and read
  notifications are kept forever. Harmless at this scale; a daily purge task would be easy to add.
- **Access tokens last 24 hours and there is no refresh endpoint**, as the PRD specifies. The frontend
  must send the user back to login when a token expires.
- **Email button links assume frontend routes** (`/creator/applications`, `/settings/connections`,
  `/brand/campaigns/{id}/proposals`, `/brand/campaigns/{id}`, `/settings/notifications`). They live in
  one dictionary in `apps/notifications/emails.py`; align them with the real routes.
- **Docker was never built or run** by the authors of this code (no Docker on the build machine). The
  Dockerfile and compose services are covered by structural tests only. Build them once before relying on them.
- **Local development used Python 3.13 and PostgreSQL 18**; the Dockerfile and compose file target
  Python 3.12 and PostgreSQL 16 as originally planned.
- **HSTS is opt-in.** By default production sends a one-year HSTS header only; subdomain locking and
  preload are off and need `SECURE_HSTS_INCLUDE_SUBDOMAINS` / `SECURE_HSTS_PRELOAD` (preload is refused
  without subdomains). Both are very hard to undo, so turn them on only for a domain that will always use HTTPS.
- **While Redis is down, rate limits are not enforced** (login and password reset keep working; a warning is
  logged). The YouTube connect step answers 503 until Redis is back. Findings 1 to 10 of the code review are
  all fixed; see the Review fixes section of the build report.
- **The independent whole-branch code review was not run.** The final pass was a self-review by the
  author (static checks, migration drift, a hunt for defects the tests cannot see). It found and fixed one
  defect: email retries did not actually back off. A fresh reviewer is still recommended before launch.

- **Typed Instagram/TikTok/Facebook stats need an admin** — a creator types followers, engagement and a profile link
  (on that site). The row is `review_status = pending`, `is_verified = false` and hidden from everything brands see
  (profile detail, directory cards, proposals, campaign eligibility) until an admin approves it, which sets
  `is_verified = true`. Rejecting stores a reason the creator sees; editing the numbers sends the row back to pending.
  YouTube is unchanged (Google proves it). An approved typed platform still does NOT make a creator Verified or let
  them apply: that stays YouTube-only. No notification is sent on approve or reject for now; the Accounts page shows
  the status. Existing typed rows became `pending` in migration 0005; the demo seeder treats its own typed rows as
  already approved — cost if wrong: one filter in `social.queries` and one in the profile serializer.

- **Verification now needs an admin for typed links, and the email for creators** — a creator needs a confirmed email
  AND a Google-proven YouTube channel with at least `MIN_CREATOR_FOLLOWERS` subscribers (`creator_email_unverified` is
  checked before `creator_youtube_required`). A brand needs a confirmed email AND one verified platform:
  `BrandSocialAccount.is_verified` is true for YouTube proven by Google, or for an Instagram, TikTok or Facebook link
  an admin approved (`review_status` pending, approved, rejected, plus `review_note`). Saving a typed link, or a new one,
  sets it back to pending. A pending or rejected link does not count, so `brand_has_platform` now means "has a verified
  platform". `/auth/me/` keeps `platform_connected` (true only when verified) and adds `platform_status`. YouTube accounts
  are not reviewed (the admin endpoints return 404 for them). Existing typed links became pending in migration
  `social.0006`; the demo seeder treats its demo Instagram links as approved. Superseded by the next entry.

- **YouTube no longer verifies a brand; the creator Verified badge follows the creator rule everywhere** — a brand is
  verified only by a confirmed email AND an Instagram, TikTok or Facebook link an admin approved. The brand YouTube
  Google sign-in endpoints (`/brands/me/social/youtube/connect|complete/`) and `fetch_channel_link` were removed, a typed
  `youtube` link is refused (400 `youtube_not_for_brands`), and any old brand YouTube rows are kept but hidden and ignored by
  `brand_has_platform` / `brand_platform_status`. Separately, `primary_verified` (the `is_verified` on directory cards
  and brand proposal lists) used to be the primary platform's own flag, so a creator whose primary platform was an
  approved Instagram showed "Verified". It now means `creator_is_verified`: a confirmed email AND Google-proven YouTube with
  at least `MIN_CREATOR_FOLLOWERS`, whatever the primary platform; approved Instagram, TikTok and Facebook numbers still
  show, with their own per-platform tag. `GET /creators/me/` and `GET /creators/{id}/` gain an `is_verified` field with the same meaning.

- **YouTube numbers can no longer be typed** — `PUT /creators/me/stats/youtube/` used to save typed numbers as Unverified
  and show them publicly without an admin check. It now returns 400 `youtube_from_google_only` (it replaces the 409
  `stats_verified`). Instagram, TikTok and Facebook are unchanged: typed, pending, hidden until an admin approves.

- **No negotiation: the rate is fixed by the brand.** A creator no longer sends a rate when applying. The proposal's
  `proposed_rate` is copied from the campaign's `budget` (per creator) at the moment of applying, and sending
  `proposed_rate` is refused with 400 so nobody thinks it was used. The column and the read-only response field keep
  their name, so existing proposals and the pages that show them keep working (older proposals keep the rate that was
  typed). `avg_proposed_rate` was removed from the campaign analytics because it would always equal the budget; the
  analytics page shows the total if every spot is filled instead — cost if wrong: re-add the field and the rate input.

- **A brand chooses, per campaign, whether creators may withdraw.** `Campaign.allow_withdrawal` (default true, so every
  existing campaign behaves as before). When it is false, `withdraw_proposal` answers 403 `withdrawal_not_allowed` for
  every status (pending, shortlisted and accepted) and changes nothing. The choice is made in the draft and is locked
  once the campaign is published (only drafts are editable), so a creator always applies under the rule they were
  shown. Creators see it on the campaign (`allow_withdrawal`) and on each of their proposals
  (`campaign.allow_withdrawal`). The brand can still reject a proposal; only the creator's own withdrawal is blocked —
  cost if wrong: one check in `proposals.services.withdraw_proposal`.

- **Docker removed; PostgreSQL is installed locally** — the Dockerfile, docker-compose.yml and .dockerignore were deleted,
  and the README and docs/DEPLOYMENT.md now describe a local PostgreSQL (plus optional Redis) and running gunicorn, the
  Celery worker and beat directly. Older entries above that mention Docker are history. The compose file had also
  published Postgres and Redis on every interface with default credentials, which a server deployment must never do —
  cost if wrong: anyone who wants containers writes their own files.

- **Review fixes: one channel per account, current proof, own videos, minimum followers, suspended creators** —
  (1) `YouTubeConnection.channel_id` (unique when set) is read at connect time (`channels?part=id`), so a channel
  another account uses is refused (`channel_in_use`); older connections fill it in at their next sync and a duplicate is
  left unverified. (2) A creator is Verified only while the proof is current: stats with `is_outdated` (access ended,
  subscribers hidden) no longer count in `creator_is_verified`, the directory flag or applying, and applying says
  `creator_youtube_reconnect`. (3) A YouTube deliverable must be a video on the creator's own channel: checked when it is
  saved (needs `YOUTUBE_API_KEY`; skipped when Google cannot answer or the channel is not known yet) and again before
  the daily sync stores any number, which also clears numbers stored earlier for someone else's video. (4) The campaign's
  minimum followers is enforced when the creator has numbers for the campaign's platform (`not_eligible`); a creator
  with no numbers on that platform is NOT blocked, because a verified YouTube creator may apply to any platform
  (earlier decision above) — cost if wrong: require numbers on the campaign's platform in
  `campaigns.eligibility.minimum_followers_problem`. (5) `accept_proposal` refuses a suspended creator
  (`creator_unavailable`); rejecting still works.
