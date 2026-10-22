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

## Contents

Click a title to jump to that section. Every section ends with a "Back to contents" link.

### Start here

- **[The idea in one minute](#the-idea-in-one-minute)**: what the platform is, in four steps
- **[Run the project](#run-the-project)**: copy-and-paste steps for Windows
  - [Before you start (install once)](#before-you-start-install-once)
  - [Step 1: Start the database](#step-1-start-the-database)
  - [Step 2: Start the API](#step-2-start-the-api-terminal-1)
  - [Step 3: Start the website](#step-3-start-the-website-terminal-2)
  - [Step 4: Open the site](#step-4-open-the-site)
  - [Next time you start it](#next-time-you-start-it)
  - [Check that it works](#check-that-it-works)
  - [If it does not start](#if-it-does-not-start)
  - [No Docker (your own PostgreSQL)](#no-docker-your-own-postgresql)
- **[Demo data](#demo-data)**: example accounts to log in with

### What it does

- **[Features](#features)**: everything the platform does
  - [For everyone](#for-everyone): sign-up, login, forgot password, notifications
  - [For creators](#for-creators): profile, YouTube, finding work, applying
  - [For brands](#for-brands): verification, finding creators, campaigns, proposals, reviews
  - [Notifications and email](#notifications-and-email)
  - [For admins](#for-admins)
  - [Behind the scenes](#behind-the-scenes): security, limits, background jobs
  - [What it does not do (on purpose)](#what-it-does-not-do-on-purpose)
- **[Who can do what](#who-can-do-what)**: the verification rules for brands and creators

### Set it up

- **[Requirements](#requirements)**: what to install
- **[Email](#email)**: where codes go, and how to send real emails
- **[Admin accounts](#admin-accounts)**: how to make an admin
- **[Photos and videos](#photos-and-videos)**: pictures and campaign media
- **[Connecting YouTube (Google sign-in)](#connecting-youtube-google-sign-in)**: Google setup
- **[Configuration](#configuration)**: every setting in `.env`

### For developers

- **[Tests](#tests)**: how to run the tests
- **[Background workers](#background-workers)**: emails, daily YouTube refresh, closing campaigns
- **[How the API behaves](#how-the-api-behaves)**: login, errors, lists, limits
- **[Project layout](#project-layout)**: what each folder holds
- **[Working on this repository](#working-on-this-repository)**

### Help

- **[Troubleshooting](#troubleshooting)**: common problems and fixes
- **[Known issues](#known-issues)**: things that are not finished

[↑ Back to contents](#contents)

## Features

This is everything the platform does today, grouped by who uses it. Words in **bold** are the names you will see in the
website.

### The idea in one minute

There are two kinds of people. **Creators** are small influencers (roughly 1,000 to 100,000 followers). **Brands** are
businesses that want creators to promote them.

1. A brand writes a **campaign** (a job post) with a budget and a deadline.
2. Creators find it and send a **proposal** (an application).
3. The brand looks at the proposals and **shortlists**, **accepts** or **rejects** each one.
4. After the work, the creator sends links to what they posted, the brand marks the job **completed**, and leaves a
   **review**.

There is no payment and no chat inside the platform. It only handles finding each other and the proposal steps.

### For everyone

| Feature | What it does |
|---|---|
| **Sign up** | Choose Creator or Brand first, then fill in name, email, username, password (8+ characters) and mobile number. The role cannot be changed later. |
| **Log in and out** | Use your email or your username. The website sends you to the creator or brand home page. Logging out ends the session. |
| **Forgot password** | Enter your email and a 6-digit code is sent. The code works once, for 10 minutes, and stops after 5 wrong tries. A new password signs you out of every device. The reply is the same whether or not the email exists, so nobody can find out who has an account. |
| **Email check** | After sign-up a 6-digit code is emailed to confirm the address. You can use the site before confirming, but some actions need it (see "Who can do what"). |
| **Notifications** | A bell with a number badge, a list of recent events, and "mark as read" or "mark all as read". See "Notifications and email" below. |
| **Notification emails** | The same events can also be emailed. Each person can switch this off in **Notification settings**. Only confirmed email addresses receive them. |
| **Privacy and Terms pages** | Public pages that explain what data is kept and the house rules. |
| **Phone and desktop** | The website works on both. Pictures that are missing or fail to load show the person's initials instead. |

### For creators

**1. Profile**
- **Photo, bio, niche** (Fitness, Tech, Beauty, Food, Travel or Other), **primary platform**, **country and city**
  (picked from lists, Bangladesh first), and **rates** per post, per story and per video.
- **Profile completion** shows how much of the profile is filled in.
- **Portfolio**: up to 10 links to past work, each with a short caption. You can pick items from your recent YouTube
  videos.
- **Public profile**: logged-in brands can see all of this, plus your stats and reviews. Nobody who is logged out can.

**2. Connecting YouTube (this makes you Verified)**
- Press **Connect YouTube** and sign in with Google. Only read-only access is asked for.
- The platform then reads your channel link, subscriber count, an engagement rate worked out from recent videos, and
  your recent videos. These show on your profile with a **Verified** badge and the time they were last updated.
- **You need at least 1,000 subscribers** to be Verified. A smaller channel stays connected but is **not Verified** and
  cannot apply, and the website tells you how many subscribers you have and how many you need. The channel is checked
  again every day (and when you press Refresh), so you become Verified once you pass the minimum, and lose it if you drop
  below. The minimum is the setting `MIN_CREATOR_FOLLOWERS`.
- Stats refresh by themselves every day. You can also press **Refresh** (once every 15 minutes).
- If Google access ends, you get a "please reconnect" notification. Your last numbers stay visible, marked **outdated**.
- **Disconnect** deletes the stored access and gives it back at Google. Your last numbers stay but become Unverified.
- **Instagram, TikTok and Facebook:** on **Accounts**, each one has a small form. Type your followers, your engagement
  rate (0 to 100) and your profile link (it must be a page on that website), then press Add. You can Edit or Remove it
  later.
  - The numbers are **Waiting for admin** at first, and **only you can see them**. An admin opens your link and checks
    them.
  - When the admin **approves**, they are **Verified** and show on your profile. If the admin **rejects**, you see the
    reason; fix the details and save to send them again.
  - Changing the numbers later sends them back to the admin.
  - They never count towards being a Verified creator or applying to campaigns. Only a confirmed email and a connected
    YouTube channel do.

**3. Finding work**
- **Find work** lists published campaigns. Filter by keyword, niche, platform, budget range and deadline.
- Every card shows brand, category, budget per creator, platform, deadline and how many creators are needed.
- An **Eligible** or **Check fit** tag compares the campaign's platform and minimum followers with your stats. It is
  only a hint. It never stops you from applying.
- The campaign page shows the full details and any photos or video. It says "Brand has selected all creators" when the
  places are full.

**4. Applying and tracking**
- **Apply now** opens a form: cover message, up to 3 portfolio links (filled in from your profile), and an experience
  note. **There is no price to type and no negotiation:** every creator gets the fixed rate the brand set on the
  campaign (its *budget per creator*), and the form shows it. **You cannot apply until your email is confirmed and a
  YouTube channel is connected with at least 1,000 subscribers.**
- One live proposal per campaign. A sent proposal cannot be edited.
- **My proposals** lists every application with its status: Pending, Shortlisted, Accepted, Rejected or Withdrawn.
- **Can you withdraw?** Each brand decides this when it posts the campaign, and the campaign page shows it as
  **Withdrawing: Allowed / Not allowed** before you apply (the apply form also warns you).
  - **Allowed:** you can withdraw a Pending, Shortlisted or Accepted proposal. Withdrawing an accepted one needs a short
    reason (up to 300 characters) and frees the place for someone else. You can apply again after withdrawing, but only
    while the campaign is still open.
  - **Not allowed:** once you apply you cannot take the proposal back. The Withdraw button is replaced by a note.
  - A rejected proposal cannot be sent again.

**5. After you are accepted**
- Add **deliverables**: the link to each post you published, the platform, and an optional note. You can change them
  until the brand marks the work completed.

**6. Home page (dashboard)**
- One clear **next step** (for example "Connect YouTube", "Finish your profile" or "Find your next campaign").
- Numbers: proposals sent, waiting for a reply, accepted, and success rate.
- Active collaborations, your latest proposals, new campaigns that might fit, and the state of your profile and YouTube.

### For brands

**1. Company profile**
- Company name, industry, website, "about" text and a **logo**. Logged-in creators can see it on your campaigns.

**2. Two steps to be fully verified**
- **Confirm your email** with the 6-digit code.
- **Get one platform verified** on **Accounts**. Any one is enough.
  - **YouTube** is connected with Google sign-in. The platform reads the channel link once, then gives the Google access
    back. It is tagged **Verified** at once.
  - **Instagram, TikTok and Facebook** are your official page link. The platform checks it is on that site, then an
    **admin opens it and approves or rejects it**. It shows **Waiting for admin**, then **Verified**, or **Rejected**
    with the admin's reason (remove it and add the correct link). A waiting link does not count.
- Until both steps are done, a brand can still browse, save drafts, shortlist and reject. It **cannot publish a
  campaign or accept a proposal**.

**3. Finding creators**
- **Find creators** is a searchable directory of creator profiles. Filters: name or username, niche, platform,
  followers (from and to), engagement rate, location, rate range, **Verified accounts only**, and minimum rating.
- Sort by followers, engagement, rate or rating. Results come in pages.
- A creator's page shows their profile, rates, stats with the Verified badge and last update time, portfolio and
  reviews.

**4. Campaigns**
- Fields: title, description, niche, platform, **budget per creator**, **deadline**, deliverables (for example
  "2 posts, 1 reel"), **creators needed** (1 to 20), and an optional **minimum followers**.
- You can attach **up to 2 photos or 1 video** while it is a draft (photos: JPG, PNG, WebP up to 5 MB; video: MP4 or
  WebM up to 50 MB).
- **Can creators withdraw?** When you post a campaign you choose one of two options: **Creators can withdraw** (the
  default) or **Creators cannot withdraw** (a creator who applied cannot take the proposal back, so you get a firm
  commitment). Creators see your choice before they apply. It is part of the draft, so it **cannot be changed after you
  publish**.
- Life of a campaign:

  | Step | What you can do |
  |---|---|
  | **Draft** | Edit everything or delete it. Creators cannot see it. |
  | **Published** | Creators can see and apply. It can no longer be edited or deleted, only closed. |
  | **Closed** | No new applications. You can still answer proposals already received. A closed campaign is never reopened. |

- A campaign **closes by itself** when its deadline passes (checked every 5 minutes), and you are told. It does **not**
  close just because all the places are filled.

**5. Handling proposals**
- Each campaign has a list of proposals, newest first, that you can filter by status. Withdrawn ones are hidden unless
  you ask for them. A counter shows, for example, "2 of 3 creators accepted".
- Each proposal shows the creator, niche, platform, followers, engagement, their rate, cover message, links, experience
  note, status (and the reason if an accepted creator withdrew) and a link to their full profile.
- Actions: **Shortlist**, **Accept** or **Reject**. The creator is notified each time.
  - You cannot undo Accept or Reject. An accepted place opens up again only if the creator withdraws.
  - **Accepted can never be more than "creators needed"**, even if two accepts happen at the same moment. When full you
    see "All creators for this campaign have already been selected." Shortlist and Reject still work.
  - Pressing Accept twice is harmless.
  - These actions still work after the campaign is closed.

**6. After the work**
- See each accepted creator's **deliverables** on the campaign page.
- Mark each collaboration **Completed**. This is final and is tracked for each creator separately.
- Leave a **review**: 1 to 5 stars and an optional note (up to 500 characters). One review per completed job. Reviews
  cannot be edited. The creator's average rating and review count update by themselves and show on their profile, in the
  directory and on proposals.

**7. Campaign statistics**
- **Page views**: how many times creators opened the campaign page. Every opening counts, so the same creator can add more than one.
- **Proposal funnel**: received, shortlisted, accepted, rejected and withdrawn.
- **Accepted compared with needed**, the **total if every spot is filled** (the rate is fixed, so creators cannot
  negotiate it), and the **acceptance rate**.
- **Content performance**: views, likes, comments and engagement for each deliverable on YouTube. This needs a YouTube
  API key on the server. Without one it shows "not available".

**8. Home page (dashboard)**
- A **"What needs your attention"** list: confirm your email, connect a platform, proposals waiting for a decision,
  shortlisted creators and drafts not yet published.
- Numbers: live campaigns, new proposals, shortlisted and accepted. Below them, your campaigns with a progress bar and
  a "new" tag where proposals are waiting.

### Notifications and email

| Who | Gets told when |
|---|---|
| **Creator** | A proposal is shortlisted, accepted or rejected. YouTube access needs to be reconnected (once per problem, not every day). |
| **Brand** | A new proposal arrives. A creator withdraws (if they were accepted, it says a place opened). A campaign closes at its deadline. |

- Every notification appears in the website first. The email copy is extra.
- Each email has a subject naming the event, a short message and one button that opens the right page in the app. It
  never includes rates, proposal text or stats.
- Emails are sent in the background and retried if they fail. A failed email never blocks what you were doing.
- Password-reset and verification codes are always sent, even when notification emails are off.
- Suspended accounts get no emails.

### For admins

Admins cannot sign up. They are created with a command (see "Admin accounts") and log in at a separate page.

| Area | What an admin can do |
|---|---|
| **Overview** | Total users, sign-ups over time, campaigns by status, total proposals. |
| **Users** | Search and filter users. **Suspend** (the person cannot log in), **reactivate**, or **delete**. Admins cannot suspend or delete themselves. |
| **Platform reviews** | Two lists, **Creator numbers** and **Brand links**, each with Waiting, Approved and Rejected tabs. Open the link, then **Approve** (a creator's numbers become Verified and show on their profile; a brand's link lets the brand publish and accept) or **Reject** with a reason (they see it). |
| **Moderation** | **Close** any campaign and **remove** a review (the rating is recalculated). |
| **Audit log** | Every action above is saved with who did it, what, and when. All of them need a written reason, except approving something in Platform reviews. |

### Behind the scenes

- **Security**: passwords are stored as strong hashes. Login sessions last 24 hours (an admin stays logged in until they log out). Google access tokens are stored
  encrypted and never sent to the website. Sign-in with Google is protected against forgery. Every page except the
  home, login, sign-up, password-reset, Terms and Privacy pages needs a login. People can only change their own data.
- **Limits**: sign-up 5 a minute, login 10 a minute, admin login 5 a minute, password reset 5 an hour, resend code 5 an
  hour and at least 60 seconds apart.
- **Reliability**: if YouTube is down, the last numbers stay with their "last updated" time. A failure in an outside
  service never breaks the rest of the platform.
- **Background jobs**: daily YouTube refresh (03:00 UTC), daily refresh of video statistics (04:00 UTC), closing
  campaigns past their deadline (every 5 minutes), and sending emails.
- **Demo data**: one command fills the site with example creators, brands, campaigns and proposals.
- **API docs**: a web page at `/api/docs/` lists every request the server understands, and the same list is saved in
  `docs/openapi.yml`.

### What it does not do (on purpose)

- No payments and no chat or negotiation. The proposal is a simple status flow.
- No push notifications, email digests or marketing emails.
- A user cannot delete their own account yet. They must contact the team, and an admin does it.
- Creators cannot review brands.
- Instagram, TikTok and Facebook are not connected automatically. Creators type the numbers and an admin checks the
  link by hand before they show on the profile.
- While the Google app is in "Testing" mode, only the listed test users can connect YouTube, and Google asks them to
  reconnect about once a week.

[↑ Back to contents](#contents)

## Who can do what

| | Checks | Can do only after verification |
|---|---|---|
| **Brand** | **Email** (a 6-digit code emailed after sign-up) and **one verified platform**: YouTube (Google sign-in), or an Instagram, TikTok or Facebook link **an admin approved** | Publish a campaign, accept a proposal |
| **Creator** | **Email** (a 6-digit code emailed after sign-up) **and** **YouTube** (connect a channel with Google sign-in, with **at least 1,000 subscribers**: Verified stats) | Apply to a campaign (needs both) |

- Unverified accounts can still log in, browse, edit their profile and (brands) save drafts, shortlist and reject.
- **Everyone** confirms their email with the 6-digit code sent after sign-up (brands and creators). The same address
  is used to reset a forgotten password and for notification emails. A creator is only *Verified* with a confirmed
  email **and** a connected YouTube channel with **at least 1,000 subscribers** (the setting `MIN_CREATOR_FOLLOWERS`),
  and **cannot apply until both are true**.
- **Forgot password** works for every account, verified or not.
- **A brand is fully verified only with both**: a confirmed email *and* one verified platform. YouTube is connected with
  Google sign-in (proven, *Verified* at once). Instagram, TikTok and Facebook are the brand's official page link; it
  counts only after an **admin approves it** (Admin, Platform reviews, Brand links). Waiting and rejected links do not
  count. Removing the last verified platform blocks the brand again. Brands manage this on **Connected accounts**
  (`/brand/<your username>/accounts`).
- The errors are 403 `brand_email_unverified`, 403 `brand_platform_required` (no verified platform; a link waiting for
  an admin does not count), 403 `creator_email_unverified`, 403 `creator_youtube_required` (no YouTube connected) and
  403 `creator_followers_too_low` (connected, but under the minimum; the message says how many
  subscribers the channel has and how many are needed).
- This is stricter than the PRD. See "Verification gates" in [`docs/DECISIONS.md`](docs/DECISIONS.md).

[↑ Back to contents](#contents)

## Requirements

- Python 3.12 or newer
- Node 20 or newer (for the website)
- PostgreSQL 16 and Redis 7. Docker is the easiest way to get both; native installs also work (see below)

The test suite needs a real PostgreSQL, because the "accepted never exceeds Creators Needed" guarantee relies on
row locks that SQLite does not have.

[↑ Back to contents](#contents)

## Run the project

These steps are for **Windows** and start with the project already on your computer. The project is two programs that run
side by side: the **API** (the server, port 8000) and the **website** (port 5173). You start each one in its own terminal
window. The default settings in `.env.example` work as they are, so you do not need to edit anything.

**How to open a terminal in the project folder:** open the project folder in File Explorer (the folder that contains
`manage.py`), click the address bar at the top, type `cmd` and press Enter.

### Before you start (install once)

| You need | Why | Check it |
|---|---|---|
| **Python 3.12 or newer** | runs the API | `python --version` |
| **Node 20 or newer** | runs the website | `node --version` |
| **Docker Desktop** | runs the database (PostgreSQL) and Redis for you | `docker --version` |

No Docker? Use [No Docker](#no-docker-your-own-postgresql) instead of Step 1.

### Step 1: Start the database

Open **Docker Desktop** and wait until it says it is running. Then, in a terminal in the project folder:

```powershell
docker compose up -d db redis
```

### Step 2: Start the API (Terminal 1)

Copy the whole block and paste it into a terminal opened in the project folder:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements/dev.txt
copy .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

It is working when you see `Starting development server at http://127.0.0.1:8000/`. **Leave this window open.**
(`seed_demo` fills the site with example creators, brands and campaigns so there is something to look at.)

### Step 3: Start the website (Terminal 2)

Open a **second** terminal in the project folder and paste:

```powershell
cd frontend
npm install
npm run dev
```

It is working when you see `Local: http://localhost:5173/`. **Leave this window open too.**

### Step 4: Open the site

Go to **http://localhost:5173** and log in with the demo accounts (password for all of them: `DemoPass123!`):

| Log in as | What you see |
|---|---|
| `demo_brand_01` | A brand with campaigns and proposals |
| `demo_creator_001` | A creator who can apply to campaigns |
| `demo_creator_005` | A creator who has not connected YouTube yet |

You can also click **Create an account** and sign up. Verification codes appear in the API window (Terminal 1), because
emails are printed there while you test. To make an admin account, see [Admin accounts](#admin-accounts).

### Next time you start it

The first-time setup is done. Next time you only need these. Open Docker Desktop first.

**Terminal 1**, in the project folder:

```powershell
docker compose up -d db redis
.venv\Scripts\activate
python manage.py runserver
```

**Terminal 2:**

```powershell
cd frontend
npm run dev
```

To stop, press `Ctrl + C` in each window. To stop the database too, run `docker compose stop`.

### Check that it works

| Open this | You should see |
|---|---|
| http://localhost:5173 | The CollabNest website |
| http://localhost:8000/api/v1/health/ | `{"status": "ok", "database": "ok"}` |
| http://localhost:8000/api/docs/ | The list of everything the API can do |

(`http://localhost:8000/` on its own shows "Not Found". That is normal: port 8000 is only the API.)

### If it does not start

| What you see | What to do |
|---|---|
| `docker: ... daemon is not running` or "cannot connect" | Open Docker Desktop and wait until it says it is running, then run the command again. |
| `python` is not found | Try `py -3.12 -m venv .venv` instead of `python -m venv .venv`. |
| PowerShell says running scripts is disabled | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then the `.venv\Scripts\activate` line again. |
| The health page says the database is not OK | The database is not running. Run `docker compose up -d db redis` (or start PostgreSQL). |
| "port already in use" | Something else uses port 8000 or 5173. Close it, or stop the old copy of this project with `Ctrl + C`. |
| `.env` is missing | Run the copy line again: `copy .env.example .env`. |

More fixes are in [Troubleshooting](#troubleshooting).

### No Docker (your own PostgreSQL)

Use this if you cannot install Docker. Do these **instead of Step 1**, then follow Steps 2 to 4 as written.

1. **Install PostgreSQL 16** and remember the password you choose for the `postgres` user.
2. **Create the database.** In a terminal:

   ```powershell
   & "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -c "CREATE DATABASE microinfluencers;"
   ```

3. **Match the password.** In the `.env` file (created in Step 2), the line `DATABASE_URL` must use your password:
   `DATABASE_URL=postgres://postgres:YOUR_PASSWORD@localhost:5432/microinfluencers`. If your password is `postgres`,
   leave it as it is.
4. **Redis.** Either install Redis 7 (through WSL, or a Redis-compatible server such as Memurai), or run
   **without Redis**. Without it the site works except for two things: rate limiting is skipped, and
   **Connect YouTube** does not work. To run without it, create a file `config\settings\local.py` with exactly this:

   ```python
   from .dev import *  # noqa: F401,F403

   CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
   ```

   then change this line in `.env` to:

   ```
   DJANGO_SETTINGS_MODULE=config.settings.local
   ```

   Do not commit that file. Use it only while running a single API window.

[↑ Back to contents](#contents)

## Demo data

`python manage.py seed_demo` creates 200 creators, 20 brands, 100 campaigns and their proposals, so the website has
something to show. It only runs when `DEBUG` is on, is safe to repeat (it tops up what is missing and repairs the
verification flags), and gives the same data every time. Options: `--creators`, `--brands`, `--campaigns`.

Log in as `demo_creator_001` or `demo_brand_01` with password **`DemoPass123!`**.

- Every demo brand and creator has a verified email, and every demo brand has an approved Instagram link, so they are
  fully verified.
- Every demo creator has a verified YouTube channel, except each fifth one (`demo_creator_005`, `010`, ...). Use
  those to see the "connect YouTube to apply" state.
- Every fourth demo campaign does not let creators withdraw, so you can see both choices.
- Demo accounts use fake `@demo.test` addresses, so notification emails are switched off for them. Do not point a real
  email provider at them (see "Email").

[↑ Back to contents](#contents)

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

**Emails landing in Spam.** The provider accepting a message does not mean the inbox accepts it. If the sender
(`DEFAULT_FROM_EMAIL`) is a Gmail, Outlook or Yahoo address but the mail goes out through Brevo or Resend, the inbox
provider cannot prove the mail is really from that address, so it puts it in Spam or drops it. No code can fix this;
the sender has to be proven. In order of how well it works:

1. **Best (for real users): your own domain.** In the provider (Brevo: *Senders, domains & dedicated IPs, Domains*), add
   the domain and copy the DNS records it shows (SPF, DKIM and DMARC) into the domain's DNS settings, then send from an
   address on that domain, for example `CollabNest <no-reply@yourdomain.com>`. A domain costs a few dollars a year.
2. **Good for a test project without a domain: send through Gmail itself.** Gmail then signs the mail, so it reaches
   Gmail inboxes. Turn on 2-step verification on the Google account, create an **App password**, and set
   `EMAIL_HOST=smtp.gmail.com`, `EMAIL_PORT=587`, `EMAIL_USE_TLS=True`, `EMAIL_HOST_USER=<your gmail address>`,
   `EMAIL_HOST_PASSWORD=<the app password>` and `DEFAULT_FROM_EMAIL=CollabNest <your gmail address>`. Gmail allows about
   500 mails a day this way, which is enough for a test, not for a launch.
3. **Always:** use a display name in `DEFAULT_FROM_EMAIL` (`CollabNest <address>`), keep the emails short and plain (they
   are), and ask people to check Spam and press **Not spam**. The verify and reset pages already say this.

To see what happened to one email, open the provider's logs (Brevo: *Transactional, Logs*): they show delivered,
blocked or bounced.

[↑ Back to contents](#contents)

## Tests

```bash
pytest                       # whole suite
pytest apps/proposals -v     # one app
cd frontend && npx tsc --noEmit    # type-check the website
```

Tests use `config.settings.test` (set in `pytest.ini`) and read `DATABASE_URL`: point it at any PostgreSQL where the
user may create databases. Email is captured in memory and background tasks run immediately, so the tests need
no Redis and no mail server. `tests_e2e/test_full_lifecycle.py` is a separate script that needs a running server.

[↑ Back to contents](#contents)

## Background workers

Email, YouTube syncs and campaign auto-closing run in Celery. In development they run inside the request, so you
do not need a worker. For production (or with `CELERY_TASK_ALWAYS_EAGER=False`):

```bash
celery -A config worker -l info --pool=solo   # --pool=solo is required on Windows
celery -A config beat -l info                 # the scheduler; run exactly ONE instance
```

Scheduled jobs (UTC): every creator's YouTube stats refresh at 03:00, published-video statistics refresh at 04:00,
and campaigns whose application deadline has passed are closed every 5 minutes.

[↑ Back to contents](#contents)

## Admin accounts

Admins cannot register through the website or the API. Create one on the server, with the backend environment
active and the database running:

```bash
python manage.py create_admin --email you@example.com --username admin
```

The password is prompted for twice and is never accepted as an argument. The command refuses a weak password: at least 12 characters, not a common one such as `12345678`, not only digits, and
not like the username or email. The admin can delete accounts, so choose a long password that you use nowhere else. To
change an admin's password later:

```bash
.venv\Scripts\python.exe manage.py changepassword admin
```

An admin **stays logged in** until they press **Log out** (the login does not expire, and it is remembered after the
browser closes). Logging out, or changing the admin's password, ends every login made before. To make admin logins
expire, set `ADMIN_TOKEN_MINUTES` to a number of minutes.

Admins sign in at **http://localhost:5173/admin/login** (through the API: `POST /api/v1/admin/auth/login/`). The
admin area has an overview, a user list (search, suspend, reactivate, delete), platform reviews (approve or reject
creators' typed Instagram, TikTok and Facebook numbers and brands' typed links) and an audit log. The public login
page rejects admin accounts, and ordinary accounts cannot use the admin login. Every admin action is recorded in
`GET /api/v1/admin/actions/`; all need a written reason except approving something in Platform reviews.

[↑ Back to contents](#contents)

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

[↑ Back to contents](#contents)

## Connecting YouTube (Google sign-in)

Only YouTube connects through OAuth. Instagram, TikTok and Facebook are typed by the creator and become Verified only
after an admin approves them (see the PRD for why they cannot be connected). Connecting YouTube is also what makes a creator Verified.

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

[↑ Back to contents](#contents)

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
| `MIN_CREATOR_FOLLOWERS` | Subscribers a creator's YouTube channel needs to be Verified and apply to campaigns. Default `1000`. |
| `ADMIN_TOKEN_MINUTES` | Minutes an admin login lasts. Default `0` = the admin stays logged in until Log out or a password change (everyone else: 24 hours). |
| `YOUTUBE_API_KEY` | Optional server key for public video statistics. Without it, content performance shows `not_available`. |
| `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` | Email delivery: console in development, SMTP for real email. |
| `DEFAULT_FROM_EMAIL` | The sender address (set up SPF/DKIM for its domain). |
| `MEDIA_URL`, `MEDIA_ROOT` | URL and folder for uploaded files. `MEDIA_ROOT` empty means `<repo>/media`. |
| `CELERY_TASK_ALWAYS_EAGER` | Development only, default `True`: run background jobs inside the request. |

Settings modules: `config.settings.dev` (local), `config.settings.test` (pytest) and `config.settings.prod`
(deployment; it refuses to start with an unsafe configuration). **Production is the default**: `manage.py`, wsgi and
Celery start in production mode unless `DJANGO_SETTINGS_MODULE` says otherwise, so a server that forgets the
variable fails to start instead of running in debug mode. The `.env` you copy already selects development.

[↑ Back to contents](#contents)

## How the API behaves

- **Auth:** `POST /api/v1/auth/login/` with `{"identifier", "password"}` (email or username), then send
  `Authorization: Bearer <token>`. Tokens last 24 hours (an admin's does not expire unless `ADMIN_TOKEN_MINUTES` is set). Logging out, resetting or
  changing a password signs the user out everywhere.
- **Errors:** always `{"error": {"code", "message", "details"}}`. Branch on `code`.
- **Lists:** `count`, `next`, `previous`, `results`; `?page=` and `?page_size=` (max 50).
- **Roles:** creators and brands see different endpoints; the wrong role gets 403 and another account's data is 404.
- **Rate limits:** register 5/min, login 10/min, admin login 5/min, password reset 5/hour, email verify 20/hour, email
  resend 5/hour (and a 60-second wait between codes).

[↑ Back to contents](#contents)

## Project layout

```
config/             settings (base / dev / test / prod), URLs, Celery
apps/core/          shared plumbing: error format, pagination, permissions, email queue, demo data
apps/accounts/      users, registration, login, password reset, email verification
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

[↑ Back to contents](#contents)

## Troubleshooting

| Problem | Cause and fix |
|---|---|
| `docker compose` cannot connect, or "docker engine not running" | Docker Desktop is not running yet. Start it and wait until it says it is running, or use native PostgreSQL and Redis. |
| "Invalid line" warnings when the backend starts | `.env` has a blank line containing a space, or was saved with a byte-order mark. Save it as plain UTF-8 and remove blank-space lines. |
| Connecting YouTube returns 503 or an empty link | Redis is not reachable (see "Without Docker"), or the Google variables are empty. |
| After Google sign-in the browser lands on a dead page | `FRONTEND_URL` is wrong. Use `http://localhost:5173` in development. |
| No email arrives (or it is in Spam) | See "Emails landing in Spam" in the email section. With the console backend, read the code in the backend terminal. With SMTP, check the sender is verified at the provider. Brevo needs its SMTP login, not your account email; Resend without a verified domain only delivers to your own address. |
| A brand cannot publish or accept (403 `brand_platform_required`) | Connect YouTube on **Connected accounts**, or add an Instagram, TikTok or Facebook link and wait for an admin to approve it (Admin, Platform reviews, Brand links). |
| A brand cannot publish or accept (403 `brand_email_unverified`) | Verify the email with the code (shown in the backend terminal in development). |
| A creator cannot apply (403 `creator_youtube_required`) | Connect YouTube. Manually typed stats do not count. |
| A creator cannot apply (403 `creator_email_unverified`) | Confirm the email with the 6-digit code. |
| A creator cannot apply (403 `creator_followers_too_low`) | The channel has fewer subscribers than `MIN_CREATOR_FOLLOWERS` (1,000 by default). It becomes Verified at the next daily sync after it grows, or when the creator presses Refresh. |
| Uploaded pictures are missing | They live in `media/`. If you set `MEDIA_ROOT` yourself, keep the same folder between runs. |
| Tests cannot create a database | `DATABASE_URL` must name a PostgreSQL user that may create databases. |

[↑ Back to contents](#contents)

## Known issues

- No known issues right now. An admin approves Instagram, TikTok and Facebook links and numbers by hand (see "Who can do
  what"), by design. Nobody is notified when an admin approves or rejects; they see the status on their Accounts page.

[↑ Back to contents](#contents)

## Working on this repository

Work on a feature branch and open a pull request into `main`. When you change an endpoint, regenerate the API file
(a test fails if it is stale):

```bash
python manage.py spectacular --file docs/openapi.yml
```

[↑ Back to contents](#contents)
