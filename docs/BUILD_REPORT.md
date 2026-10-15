# Build report: everything that was done

This report explains, in simple words, what was built for the Micro-Influencers' Platform backend, how it
was built, what went wrong along the way, and what is still open. It is written for people who were not
watching the work happen.

---

## 1. The project in one minute

The platform is a **marketplace with two sides**:

- **Creators** (micro-influencers, people with roughly 1,000 to 100,000 followers) make a profile, show
  their numbers and prices, and **apply** to campaigns.
- **Brands** (small and medium businesses) **post campaigns**, search for creators, and **accept or reject**
  the applications they receive.

The goal from the product document (the PRD): a brand should be able to find a good creator in a few
minutes, a creator should be able to apply without leaving the platform, and every application should
always have a clear status, with nothing lost or unclear.

My job was the **backend**: the server that stores the data and enforces the rules. The frontend (the
screens people click on) is built by another team and talks to this server through an **API** (a list of
web addresses it can call).

## 2. How I worked

**Step 1: I read the PRD** and explained the project back to you.

**Step 2: I wrote a plan** (`plan.md`). It has 30 small tasks in 10 phases. Every task says exactly which
files to make, what each function is called, and which tests prove it works. I also listed in advance
the "risky situations" a real user might hit that the PRD does not mention (I call them the *Review
Focus*), so that I would test for them on purpose.

**Step 3: I built it phase by phase**, one phase per request from you, in this order:

| Phase | What it covers | Tasks |
|---|---|---|
| 0 | Project foundation | 1–2 |
| 1 | Sign up, log in, password reset | 3–6 |
| 2 | Profiles, audience numbers, portfolio | 7–9 |
| 3 | In-app notifications | 10 |
| 4 | YouTube connection | 11–13 |
| 5 | Creator search, campaigns | 14–16 |
| 6 | Applications (proposals) | 17–20 |
| 7 | Home screens (dashboards) | 21–22 |
| 8 | Security, speed, documentation, packaging | 23–25 |
| 9 | Extras: emails, deliverables, reviews, admin, analytics | 26–30 |

**The method for every task** was the same, called *test-first*:

1. Write the tests that describe what should happen.
2. Run them and **watch them fail** (this proves the tests can actually catch a problem).
3. Write the smallest code that makes them pass.
4. Run **all** the tests again.
5. Save the work in git (a "commit") and write a line in a progress notebook.

I also kept a **progress notebook** (a "ledger") with one line per finished task and a line for every
decision I made that was not spelled out in the PRD. Those decisions are now in `docs/DECISIONS.md`.

**Each phase lives on its own git branch** (`feature/phase-0-foundation` … `feature/phase-9-extensions`).
Each branch was cut from the one before it, so the last branch contains everything. Later, the last branch
(`feature/phase-9-extensions`) was pushed to GitHub and merged into `main` through pull requests #1 and #2.
The earlier phase branches exist only on this computer.

## 3. The tools I chose (and why)

| Tool | Why |
|---|---|
| **Python + Django 5.2** | You said the project uses Django. It is the main framework. |
| **Django REST Framework** | Makes building an API in Django simple and standard. |
| **PostgreSQL** | A real database. The "never accept more creators than needed" rule needs *row locks*, which only a real database like this gives. |
| **Celery + Redis** | Runs slow jobs *in the background* (sending email, syncing YouTube) so users never wait. Redis is also where the "too many attempts" counters live. |
| **JWT tokens** | The "ticket" a user gets after logging in. It lasts 24 hours. |
| **drf-spectacular** | Builds the interactive API documentation (Swagger) from the code itself. |
| **pytest** | Runs the tests. |

Local note: your machine had no Docker and no PostgreSQL, so I installed a small PostgreSQL inside the
project's private Python folder (`.venv`) just to run the tests. The project files still say PostgreSQL 16
and Python 3.12 for real deployment; I developed on Python 3.13 and PostgreSQL 18.

## 4. What I built, phase by phase

### Phase 0: Foundation (Tasks 1–2)

- A working Django project with separate settings for **development**, **testing** and **production**.
- A **health check** address (`/api/v1/health/`) that says "I am alive and can reach the database".
- **Deny by default:** every new address requires a login unless it says otherwise. A test proves this
  (I loosened the rule on purpose and the test failed, so I know it works).
- **One error format** for every problem: `{"error": {"code", "message", "details"}}`. The frontend can
  rely on `code`.
- Standard pages of 20 results (maximum 50), and the "creator / brand / admin" permission checks.
- Safe-input helpers: they strip HTML from text and only allow normal `http(s)` links (so nobody can store
  a `javascript:` link that would run code on someone's screen).
- The Swagger documentation page at `/api/docs/`.

### Phase 1: Accounts (Tasks 3–6)

- **Sign up:** choose creator or brand first, then fill name, email, username, password (8+ characters)
  and phone. Email and username must be unique, ignoring capital letters. Nobody can sign up as admin.
- **Log in** with email *or* username. The error is the same for "wrong password" and "no such user", so
  nobody can use it to find out who has an account.
- **Log out** really works: every login ticket carries a version number. Logging out or resetting the
  password raises the user's number, so all old tickets stop working at once.
- **Password reset by email code:** a 6-digit code, valid 10 minutes, works once, locked after 5 wrong
  tries, stored only as a scrambled value. The message is the same whether or not the email exists.
  Resetting a password signs the person out everywhere. Two people using the same code at the same moment
  is handled: only one wins.
- **Email sending in the background**, so a broken email provider never makes a page slow or fail.
- **Rate limits** (too many tries in a short time are refused) on login, sign up and reset.

### Phase 2: Profiles (Tasks 7–9)

- **Creator profile:** photo link, bio, niche (Fitness, Tech…), main platform, city and country, three
  prices (post, story, video), and a **profile completion %**. A missing photo is returned as `null` so
  the frontend can draw an initials avatar.
- **Brand profile:** company name, industry, website, logo, about.
- **Audience numbers per platform** (followers, engagement rate). Numbers typed by hand are labelled
  **Unverified**. Typing over a number that came from YouTube is refused.
- **Portfolio:** up to 10 links to past work. Ten requests at the same instant still cannot create an
  11th item.

### Phase 3: Notifications (Task 10)

- One single function creates every notification, so nothing is missed.
- The bell badge number counts **all** unread notifications (not just the page you can see).
- Mark one or all as read.

### Phase 4: YouTube (Tasks 11–13)

- A creator can **connect their YouTube channel** through Google's official login. We only ask for
  **read-only** permission and show a consent screen.
- The Google tokens are **encrypted** in our database and are **never** sent to the frontend.
- The follower count and engagement rate (likes + comments ÷ views over the last 10 videos) are pulled
  automatically, and a connected account gets the **Verified** badge.
- A background job refreshes everyone **every day at 03:00 UTC**. A creator can also refresh by hand, but
  only once every 15 minutes.
- If Google says the permission is gone, we keep the **last known numbers**, mark them *outdated*, and
  tell the creator **once** to reconnect (not every day).
- The connect flow uses a **signed, single-use, 10-minute "state" code** to stop forged logins.
- Disconnecting deletes the tokens and keeps the numbers as Unverified.

### Phase 5: Finding creators and campaigns (Tasks 14–16)

- **Creator directory (for brands):** search by name or username; filter by niche, platform, follower
  range, engagement range, location, price range, "verified only"; sort by followers, engagement or
  price. Creators with no numbers still appear, at the bottom. At 5,000 creators it answers in about
  20 milliseconds.
- **Campaigns:** a brand makes a **Draft**, then **Publishes** it, then it becomes **Closed**. Rules:
  only drafts can be edited or deleted; a closed campaign can never reopen; the number of creators needed
  must be 1–20 (enforced by the *database itself*, not just the code).
- **Automatic closing:** a job runs every 5 minutes and closes campaigns whose deadline passed, and tells
  the brand once. Also, the server refuses applications after the deadline *even before* that job runs.
- **Creator side:** list and filter open campaigns, with an **"eligible"** hint (do you have numbers for
  this platform, and enough followers?). The hint is only advice; it never blocks applying.

### Phase 6: Applications (Tasks 17–20): the heart of the product

- A creator applies with a cover message, a price, up to 3 links and a note. **Only one live application
  per campaign.** Two clicks at the same moment still give exactly one application.
- A rejected creator cannot apply again. After withdrawing, a creator can re-apply, but only while the
  campaign is still published.
- **Withdraw:** an *accepted* creator must give a reason (up to 300 characters) and the brand is told "a
  slot has opened".
- **The brand's list:** newest first, withdrawn hidden by default, with a counter like "2 of 3 accepted".
- **Shortlist / Accept / Reject:** allowed moves are strictly defined. Accept and Reject can't be undone.
  Accepting twice is harmless.
- **The big guarantee:** *accepted creators can never be more than "creators needed"*, even if many brand
  clicks arrive at the same instant. I did this with a **database lock** on the campaign. To prove the
  tests are real, I temporarily **removed the lock** and 12 of 32 test runs failed; I put it back, and it
  passed 60 out of 60 runs.
- The creator's own list shows every application with its status; a re-application is a new entry.

### Phase 7: Home screens (Tasks 21–22)

- **Creator dashboard:** profile %, YouTube status, 5 newest open campaigns, latest applications,
  accepted campaigns, and "proposals sent / acceptance rate".
- **Brand dashboard:** total and active campaigns, total proposals, shortlisted and accepted counts, and a
  quick link to each campaign's proposals.
- Counting rules follow the PRD: withdrawn proposals count as "sent", and a proposal that was accepted and
  then withdrawn does **not** count as accepted.
- The brand dashboard always uses 4 database queries, however much data there is.

### Phase 8: Making it safe, fast, documented (Tasks 23–25)

- **Security tests that walk every address automatically:** without a login → 401; wrong role → 403;
  only 8 addresses are public (and a test names them). New addresses are checked automatically later.
- **A real hole found and fixed:** the "too many tries" limit could be avoided by sending a fake
  `X-Forwarded-For` header with each request. I wrote a failing test first, then fixed it (`NUM_PROXIES`).
- No secret (password, token, hash) appears in any response. Errors never show internals. CORS only allows
  the frontend's address.
- **Production settings refuse to start** if something is unsafe (no secret key, wildcard hosts, no
  encryption key…), and force HTTPS. Django's own deployment checker reports zero warnings.
- **Demo data:** `python manage.py seed_demo` makes 200 creators, 20 brands, 100 campaigns. Same data every
  time, safe to repeat, only runs in debug mode. (Password: `DemoPass123!`.) I tested with 5,000 creators:
  every list answered in 7–22 ms.
- **Documentation:** README, deployment guide, Swagger with groups and explanations, and an
  `docs/openapi.yml` file for Postman. Tests fail if this file or the environment-variable list gets out
  of date.
- **Docker files** (Dockerfile + compose). *Not built here: no Docker on this computer.*
- **Clean-clone check:** I copied the repo to an empty folder, installed everything fresh, followed the
  README and ran all tests: all passed.

### Phase 9: The extras (Tasks 26–30)

- **Email notifications + email verification (FR-24):** a 6-digit code is emailed after sign up. Every
  notification can also be emailed, but only if the user is active, has a verified email and has not
  turned emails off. Emails are short, have one button, and never contain prices, messages, stats or
  names. Failed emails are retried with growing waits; they never break the page.
- **Deliverables and completion (FR-20):** an accepted creator adds links to the posts they published.
  The brand marks the collaboration **Completed** (final; each creator is tracked separately). After
  that, links are locked and the creator can't withdraw.
- **Ratings and reviews (FR-21):** after completion the brand gives 1–5 stars and optional text (max 500).
  One review each, no editing. The creator's average and count update automatically (even when many
  reviews arrive at once). Brands can filter the directory by minimum rating and sort by rating.
- **Admin panel (FR-22):** admins are created on the server (`create_admin`, password typed in a prompt,
  never in a command line). Admins log in on their own address. They can search users, **suspend**,
  **reactivate** or **delete** them, close campaigns and remove reviews. Every action needs a written
  reason and is saved in an **audit log** that survives even if the admin or the target is deleted.
  Admins can't suspend or delete themselves. There is also a platform overview (users, sign-ups over 30
  days, campaigns by status, total proposals).
- **Campaign analytics (FR-23):** views, the proposal funnel, accepted vs needed, average proposed price
  vs budget, acceptance rate. I also built the "content performance" part (views, likes, comments per
  delivered YouTube video). It reads a **daily saved snapshot**, so opening the page never waits for
  Google; unknown numbers say `not_available`.

## 5. Mistakes and problems along the way (and how they were fixed)

I want to be open about these:

- **Terminal trouble:** several times my long terminal commands were rejected by the shell. Nothing
  broke each time; I redid those edits with safer tools.
- **Tests that were wrong, not the code:** a few tests forgot to ask for the database, or used the clock
  wrongly. I fixed the tests.
- **Gates that stopped me:** the "run everything" check refused to record a task three times (a name that
  clashed with the documentation tool; duplicated names in the API document; an out-of-date API file).
  Each was a real inconsistency, fixed before moving on.
- **A bug I wrote and caught:** demo phone numbers used Python's `hash()`, which changes every run.
  Fixed with a stable method and a test.
- **A bug the tests could not see:** email "retry with backoff" actually waited a fixed 3 minutes each
  time. Found during my self-review, fixed with a test written first.
- **A task order change:** Task 13 (YouTube sync) had to be built before Task 12 (connect flow) because
  12 depended on 13. I recorded that decision.

## 6. The numbers

- 30 tasks, 10 phases, 10 stacked git branches
- About 220 files and 20,000+ lines added (code, tests and docs)
- **872 automated tests, all passing** (810 before the code-review fixes)
- 59 written decisions in `docs/DECISIONS.md`
- Every one of the 5 "Review Focus" risks has tests

## 7. What I could NOT check

- **Docker:** the image and compose stack were never built or started (Docker isn't installed here).
- **Real Google:** all Google behaviour was tested with fakes and mocked web calls, never with a real
  Google account or your Google keys.
- **A live server with Redis:** login/limits were tested in the test suite, not against a running Redis.
- **Real email delivery** (Gmail/Outlook): not tested; it needs your email provider set up (SPF/DKIM).

## 8. The independent code review (what it found)

At your request I reviewed the whole repo and reported **10 findings**. **All 10 have since been
fixed (each with a test that failed first).** What each fix did is in the
"Review fixes" part right after this list.
The most important:

1. `wsgi.py`, `celery.py` and `manage.py` default to **development** settings. A deployment that forgets
   to set one variable would run with debug on and a publicly known secret key (login tickets could be
   forged).
2. The Docker health check also applies to the **worker and scheduler**, which have no web port, so they
   would be reported "unhealthy" and might be restarted forever.
3. The **YouTube API key can leak into logs** when Google can't be reached.
4. The **YouTube connect "state" is not tied to the person's browser**, so one creator could trick another
   person into linking their channel to the first creator's profile.
5. A malformed notification could cause a **500 error after the data was saved**.
6. If **Redis goes down**, login/sign up/password reset fail.
7. **HSTS preload** is switched on for every production deployment.
8–10. Smaller clean-ups (a private helper used across apps, an inefficient view counter, and the daily
   YouTube sync starting everyone at the same second).

**Review fixes (findings 1 to 10, all done)**

1. `manage.py`, wsgi and Celery now start in **production** mode unless told otherwise (one shared
   helper, `config/bootstrap.py`). Local development opts in with `DJANGO_SETTINGS_MODULE=config.settings.dev`
   in `.env` (the example file has it). Docker containers are forced onto production settings.
2. The Docker image no longer has a web health check; only the `web` service has one.
3. Network errors from Google no longer contain the request address (and so the API key), and the HTTP
   library is kept from logging addresses.
4. YouTube connect now finishes in a separate step by the **logged-in** creator, and a link started by
   someone else is refused. I proved the test catches the attack by removing the check: the test failed.
5. Building a notification email can no longer raise after the data was saved: problems are logged, the
   link falls back to the app's home page, and the in-app notification is unaffected.
6. A **Redis outage** no longer breaks login, sign-up, password reset or email verification. The rate
   limiter now lets requests through (and logs a warning) when Redis can't be reached, and Redis calls give
   up after 2 seconds. While Redis is down the rate limits are **not enforced**. The YouTube connect step
   answers `503` (try again), and background jobs that can't be queued are logged instead of failing a
   request whose data was already saved. I broke the new code on purpose: 6 outage tests failed.
7. **HSTS** is now opt-in: only the one-year header is on by default. Subdomain locking and preload are
   switched on with `SECURE_HSTS_INCLUDE_SUBDOMAINS` and `SECURE_HSTS_PRELOAD` (preload without subdomains
   is refused at start-up).
8. The proposal-locking helper is now a public function in `apps/proposals/locks.py`, shared by proposals,
   deliverables and reviews (lock order: campaign, then proposal). A test forbids importing another app's
   private names.
9. The campaign view counter is one database statement (`INSERT ... ON CONFLICT`) instead of 2-3 queries,
   and has no race.
10. The daily YouTube sync is spread evenly over 30 minutes (`YOUTUBE_SYNC_SPREAD_SECONDS`) instead of
    starting every creator at once.

Other known gaps (not bugs): suspended users' campaigns/proposals stay visible; old codes and
notifications are never deleted; there is no token-refresh address (tickets last 24 hours); the email
button links assume frontend page names I chose.

## 9. How to run it

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements/dev.txt
copy .env.example .env
docker compose up -d db redis
python manage.py migrate
python manage.py seed_demo        # optional demo data
python manage.py runserver
pytest                             # run all tests
```

Open `http://localhost:8000/api/docs/` to see every endpoint. Full details: `README.md`,
`docs/DEPLOYMENT.md`, `docs/DECISIONS.md`.

## 10. What YOU need to do

The code is finished, but a few things can only be done by a person: they need your accounts, your
passwords, your decisions, or your team. They are listed in the order I suggest doing them. Tick them off
as you go.

**Time check:** the project deadline is **23 October**. The PRD says the **last 2 days (21–23 Oct) are for
bug fixes only**, so try to finish items 1 to 8 before then.

### A. Do first (today or tomorrow)

- [x] **1. The code-review problems are fixed.** All 10 findings from section 8 were fixed, each with a
  test. Nothing more to do here. Still do item 15 (a human review).

- [x] **2. The work is on GitHub.** `feature/phase-9-extensions` was pushed and merged into `main` through
  pull requests #1 and #2. For every later change, use a new feature branch and a pull request.

- [ ] **3. Give the frontend team what they need.** Send them:
  - `docs/openapi.yml`: import it into Postman or Insomnia. It lists every address, input and output.
  - The live docs page `http://localhost:8000/api/docs/` (or your server's address) once it runs.
  - `docs/DECISIONS.md` and this section 10.F ("What the frontend must know").
  Agree one thing with them now: **the page names used in email buttons** (see 10.F). I guessed them.

### B. Set up your computer properly (about 1 hour)

- [ ] **4. Install Docker Desktop** (docker.com). I could not test Docker, so you are the first to try it.
  Then, in the project folder:

  ```bash
  docker compose up -d db redis        # starts PostgreSQL and Redis
  ```

  Open your `.env` file (copy `.env.example` to `.env` first) and make sure `DATABASE_URL` and `REDIS_URL`
  point to these two (the example file already does).

- [ ] **5. Run the whole thing once, like a new person would.**

  ```bash
  python -m venv .venv
  .venv\Scripts\activate
  pip install -r requirements/dev.txt
  python manage.py migrate
  python manage.py seed_demo
  python manage.py runserver
  pytest
  ```

  Open `http://localhost:8000/api/docs/`, log in as `demo_creator_001` / `demo_brand_01` with password
  `DemoPass123!`, and click around. Also start the background workers in two more terminals:

  ```bash
  celery -A config worker -l info --pool=solo     # --pool=solo is needed on Windows
  celery -A config beat -l info                   # start only ONE of these
  ```

- [ ] **6. Test the full Docker stack once** (this is the part I could not run):

  ```bash
  docker compose build
  docker compose run --rm web python manage.py migrate
  docker compose up -d
  ```

  If something fails, send me the error text and I will fix the files. (Known issue: the worker and
  beat no longer show "unhealthy": finding 2 was fixed by moving the health check to the web service only.)

- [ ] **7. Know about the temporary database on this computer.** To run tests and the app here without
  Docker, a small PostgreSQL runs from the project's private Python folder (data in `.superpowers/pgdata`,
  port 51314). It stops when the session ends or the computer sleeps, and your local `.env` points at it.
  Once Docker or a normal PostgreSQL works for you, change `DATABASE_URL` in `.env` and stop it
  (Task Manager → end the `postgres.exe` processes). The `.superpowers` folder is not part of the product
  and is ignored by git.

### C. Create the real accounts and keys (needs your logins)

I cannot do these for you; they need your Google and email accounts.

- [ ] **8. Make the secret keys** and put them in `.env` (never in git, never in a chat):

  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(64))"
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```

  First one → `SECRET_KEY`. Second one → `OAUTH_ENCRYPTION_KEY`. **Back up the second one.** If it is lost,
  every creator has to reconnect YouTube.

- [ ] **9. Create the Google app (for the YouTube connection).** Do this early: Google can be slow.
  1. Go to the Google Cloud console and create a project.
  2. Turn on **YouTube Data API v3**.
  3. Set up the **OAuth consent screen** in **Testing** mode and add your test users' Google emails.
     (Only the people you list can connect while it is in Testing mode.)
  4. Create an **OAuth client ID** of type *Web application*. Add the redirect address
     `https://<your-backend-address>/api/v1/social/youtube/callback/` (for local tests use
     `http://localhost:8000/api/v1/social/youtube/callback/`).
  5. Copy the client id and secret into `.env`: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
     `GOOGLE_REDIRECT_URI`.
  6. *(Optional)* Create an **API key** restricted to the YouTube Data API and put it in `YOUTUBE_API_KEY`.
     Without it, the "content performance" numbers just say `not_available`.

  Remember: in Testing mode Google makes creators **reconnect about once every 7 days**. That is normal.
  The PRD also says the app needs a **Privacy Policy and Terms page** for Google's review; those pages
  are for the frontend team to make.

- [ ] **10. Choose an email provider and set it up.** Password reset **only works by email**, so this is
  required, not optional. Pick any provider that supports SMTP, then:
  1. Fill `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`,
     `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` in `.env`
     (use `django.core.mail.backends.smtp.EmailBackend` for `EMAIL_BACKEND`).
  2. Add **SPF and DKIM** records for your sender domain (your provider shows you what to add). Without
     them, mail goes to spam.
  3. **Test with real inboxes:** request a password reset to a real Gmail address and a real Outlook
     address and check that the code arrives.

- [x] **11. Create the first admin** (done on this computer for local use; repeat it on the real server). Admins cannot sign up on the website.

  ```bash
  python manage.py create_admin --email you@example.com --username yourname
  ```

  It asks for a password (twice). Then log in at `POST /api/v1/admin/auth/login/`.

### D. Before the app goes on the internet

- [ ] **12. Decide where it will run** (a server, a cloud service…). It needs: PostgreSQL 16 with backups,
  Redis 7, and a **reverse proxy** (like nginx or a cloud load balancer) that handles HTTPS. Full details
  are in `docs/DEPLOYMENT.md`. Three rules matter a lot:
  - The proxy must **set and overwrite** `X-Forwarded-Proto` and `X-Forwarded-For` (never trust the
    client's values). Otherwise people can dodge the login rate limits.
  - Port 8000 must **not** be reachable directly from the internet.
  - Run **exactly one** `beat` (the scheduler). Two would run every daily job twice.
- [ ] **13. Fill in the production settings:** `ALLOWED_HOSTS` (your real domain), `CORS_ALLOWED_ORIGINS`
  (your frontend's `https://` address), `FRONTEND_URL`, `DATABASE_URL`, `REDIS_URL`, and
  `DJANGO_SETTINGS_MODULE=config.settings.prod`. The production settings will refuse to start if
  something is unsafe, which is on purpose.
- [ ] **14. Run the safety checklist** at the end of `docs/DEPLOYMENT.md` (7 ticks), including
  `python manage.py check --deploy`.
- [ ] **15. Get a person to review the code.** I checked my own work and then ran one review over the
  whole project, but both were done by me, not by an independent person. A teammate should read the code
  before launch. A GitHub pull-request review is a good place for this.

### E. Decisions I need you to confirm

The PRD did not say what to do in these cases, so I picked a sensible answer. Please read them, and tell
me if you want any changed (each one is a small change). The full list of all 59 is in `docs/DECISIONS.md`.

| What I chose | Why | If you disagree |
|---|---|---|
| Login works with email **or** username | PRD says only "login" | Tell me which one only |
| Logging out signs the user out of **all** devices | A login ticket cannot be cancelled one by one | Say if you want per-device logout |
| Creators can open a **closed** campaign's page; only **published** ones are listed | Needed so "Apply is disabled" makes sense | Tell me if closed pages should be hidden |
| Disconnecting YouTube **keeps** the numbers but marks them Unverified | Don't lose a creator's data | Say if numbers should be deleted |
| Brands see a creator's numbers from their **main** platform only | One simple rule everywhere | Tell me if you want a per-platform view |
| Acceptance rate is a number from 0 to 1, or empty when nothing was sent | Avoids showing a fake 0% | Tell me if you want a percentage |
| The campaign does **not** close when it is full | PRD says so | (already the PRD rule) |
| Marking a collaboration "Completed" needs no deliverable first | PRD silent | Say if at least one link should be required |
| A completed collaboration **cannot be withdrawn** | "Completion is final" | Say if creators may still withdraw |
| Admin login is **separate**; normal login refuses admins | Safer, and the PRD says "separate panel" | Tell me if admins should use the normal login |
| Suspended users keep their campaigns/proposals visible | PRD only says "cannot log in" | Say if their content should be hidden |
| Strict HTTPS (HSTS) is on in production for one year; subdomains and preload are **off** | Those two are very hard to undo | Set `SECURE_HSTS_INCLUDE_SUBDOMAINS` / `SECURE_HSTS_PRELOAD` when ready |

### F. What the frontend must know

The complete guide is `docs/FRONTEND_GUIDE.md`; send that file to the frontend team. The short version:

1. **Login:** `POST /api/v1/auth/login/` with `{"identifier": "<email or username>", "password": "…"}`.
   You get `{"access": "<token>", "user": {…}}`. Send the token on every request as
   `Authorization: Bearer <token>`. It lasts **24 hours**; when it ends, send the person to the login page
   (there is no refresh address).
2. **Errors** always look like `{"error": {"code": "…", "message": "…", "details": …}}`. Use `code`
   to decide what to show. `details` holds per-field messages for form errors (HTTP 400).
3. **Lists** return `count`, `next`, `previous`, `results`. Use `?page=` and `?page_size=` (max 50).
4. **Prices and rates are strings** such as `"150.00"`. The acceptance rate is a number from 0 to 1.
5. **Missing photos/logos are `null`**: draw an initials avatar.
6. **YouTube connect has three steps** (changed after the code review, so that only the person who started
   it can finish it): (a) call `GET /api/v1/social/youtube/connect/` and send the browser to the
   `authorization_url`; (b) Google sends the person back to
   `FRONTEND_URL/settings/connections?youtube=confirm&code=…&state=…` (or `?youtube=error&reason=…`);
   (c) your page, while logged in, sends `{"state", "code"}` unchanged to
   `POST /api/v1/social/youtube/complete/`. The numbers appear a few seconds later; read
   `GET /api/v1/social/youtube/`.
7. **Email buttons link to pages the frontend must have:** `/creator/applications`,
   `/settings/connections`, `/brand/campaigns/{id}/proposals`, `/brand/campaigns/{id}` and
   `/settings/notifications`. If your real routes differ, tell me (one place to change).
8. **Campaign page for creators** has `can_apply` and `apply_blocked_reason`
   (`active_proposal`, `proposal_rejected`, `campaign_closed`), plus `all_creators_selected`.
9. **Brand proposal list** has `accepted_count` and `creators_needed` next to the results ("2 of 3 accepted").
10. **Analytics** can say `"not_available"` instead of a number: show a dash.
11. **Admin screens** use their own login address `/api/v1/admin/auth/login/`.
12. The **Privacy Policy and Terms pages** (needed by Google) are frontend work.
13. The **demo data** (`seed_demo`, password `DemoPass123!`) is the fastest way to see every screen filled in.

### G. Team and paperwork (from the PRD)

- [ ] **16. Agree the API with the frontend team** (PRD: "agreed by both teams"). `docs/openapi.yml` is
  the agreement. Whenever an endpoint changes, regenerate it with
  `python manage.py spectacular --file docs/openapi.yml` (a test fails if it is out of date).
- [ ] **17. Keep documenting research, planning, decisions and what changed** (PRD section 4.6, required
  by the internship brief). `plan.md`, `docs/DECISIONS.md` and this report are a good start; keep them
  updated as the team learns things.
- [ ] **18. Use the pull-request workflow** for every later change, and ask a teammate to review.

### H. Suggested order against the deadline

| When | Do |
|---|---|
| **13–14 Oct** | Items 1, 2, 3 (decide on fixes, push, send docs to frontend). Items 4–7 (Docker, run it once). |
| **15–16 Oct** | Items 8–11 (keys, Google app, email provider, first admin). Start joint testing with the frontend. |
| **17–20 Oct** | Fix problems found in joint testing. Items 12–15 (hosting, production settings, checklist, review). |
| **21–23 Oct** | **Bug fixes only.** Final test of password reset emails, YouTube connect, and one full campaign: create → publish → apply → accept → complete → review. |

### I. A quick "is it working?" test to do together with the frontend

Do this once everything is connected. If every step works, the main product works:

1. Register a brand and a creator. Check the verification and reset emails arrive.
2. Creator: fill the profile, connect YouTube (or type numbers by hand), add a portfolio link.
3. Brand: create a campaign, publish it.
4. Creator: find it (check the "eligible" hint), open it, apply.
5. Brand: open the proposals, shortlist, then accept. Click Accept twice quickly: the count must go up once.
6. Creator: see the status change and the notification (and email, if verified).
7. Creator: add deliverable links. Brand: mark Completed, then leave a review.
8. Check the creator's rating on the directory.
9. Admin: log in, look at the overview, suspend a test user and check they cannot log in.

## 11. Small dictionary

- **API / endpoint:** a web address the frontend calls to ask the server to do something.
- **Test-first:** write the test, see it fail, then write the code.
- **Branch / commit:** a saved copy of the work in git / one saved step.
- **Token (JWT):** the "ticket" given at login.
- **Row lock:** the database makes other requests wait so two things cannot change the same data at once.
- **Background job (Celery):** work done behind the scenes, not while the user waits.
- **Rate limit / throttle:** a limit on how many tries are allowed in a short time.
- **Migration:** a saved instruction that changes the database layout.
- **OAuth:** the safe "log in with Google" flow, so we never see a password.
- **Idempotent:** doing something twice gives the same result as doing it once.
