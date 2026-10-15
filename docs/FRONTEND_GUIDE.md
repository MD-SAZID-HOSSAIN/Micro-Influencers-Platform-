# Frontend guide

Everything the frontend team needs to build on this API. It is written from the code and from
`docs/openapi.yml`, so every field name, status code and error code below exists.

**How to use this document:** read sections 1 to 3 once. Then build screen by screen using sections 4 to 8.
Use the Swagger page (`/api/docs/`) as the exact reference for fields, and this guide for *how the pieces
fit together* and *what can go wrong*.

---

## 1. Start here

| What | Where |
|---|---|
| API base URL | `http://localhost:8000/api/v1/` in development (the real host once deployed) |
| Interactive docs (try calls in the browser) | `/api/docs/` |
| Machine-readable contract | `/api/schema/`, or the file `docs/openapi.yml` in the repo |
| Health check | `GET /api/v1/health/` returns `{"status": "ok", "database": "ok"}` |

**Generate your types and client from `docs/openapi.yml`** (for example with `openapi-typescript` or
`orval`) instead of writing them by hand. The file is checked by a test, so it is never out of date with the
backend. When the backend changes an endpoint, the file changes in the same pull request.

**Demo data for building screens.** Ask the backend developer to run `python manage.py seed_demo`. It creates
200 creators, 20 brands, 100 campaigns and their applications. Log in as `demo_creator_001` or
`demo_brand_01` with password `DemoPass123!` (demo data exists only on development machines).

**CORS.** The browser may only call the API from an address listed in the backend's `CORS_ALLOWED_ORIGINS`.
Tell the backend developer your frontend address (for example `http://localhost:3000`). If calls fail in the
browser with a CORS error but work in Postman, this is the cause.

---

## 2. Rules that apply to every call

### 2.1 Authentication

1. Log in (section 4) and keep the `access` token.
2. Send it on every other request: `Authorization: Bearer <token>`.
3. The token lasts **24 hours**. There is **no refresh endpoint**. When any call returns **401**, clear the
   stored token and send the person to the login page.
4. Logging out (`POST /auth/logout/`) invalidates **every** token the person has, on all devices. Resetting a
   password does the same. Suspending an account does too. All of these show up as a 401 on the next call.

Only these addresses work without a token: register, login, admin login, the two password-reset calls, the
health check, the Google callback and the docs pages. Everything else returns 401 without a token.

### 2.2 Roles

Every account is a `creator`, a `brand` or an `admin`. Calling an address meant for another role returns
**403**. Plan your routes the same way:

| Role | Can call |
|---|---|
| creator | `/creators/me/...`, `/campaigns/...`, `/brands/{id}/`, `/social/youtube/...` |
| brand | `/brand/...`, `/creators/` and `/creators/{id}/...`, `/brands/me/...` |
| admin | `/admin/...` only (log in at `/admin/auth/login/`) |
| any logged-in user | `/auth/me/`, `/auth/logout/`, `/auth/email/...`, `/notifications/...`, `/settings/notifications/` |

Admins cannot use the normal login, and creators or brands cannot use the admin login. Both answer with the
same `invalid_credentials` error as a wrong password.

### 2.3 Errors

Every error has the same shape:

```json
{ "error": { "code": "campaign_full", "message": "All creators for this campaign have already been selected.", "details": null } }
```

- Decide what to do from **`code`** (stable). Show **`message`** when it is a sentence for people; it is
  written to be shown as is.
- For form errors (HTTP 400, `code: "validation_error"`), `details` is an object with one entry per field:
  `{"email": ["A user with this email already exists."], "password": ["..."]}`. Show each message next to
  its field. Errors that are not about one field appear under `non_field_errors`.

| HTTP | Meaning | What the screen should do |
|---|---|---|
| 400 | Bad input (`validation_error`) or a rule failed (for example `deadline_in_past`) | Show the messages |
| 401 | No token, bad token, expired token, or suspended account | Go to login (but on the login form itself, show the message) |
| 403 | Wrong role for this address | Should not happen if routes match roles; show "not allowed" |
| 404 | Does not exist, or belongs to someone else, or is a draft you may not see | Show "not found" |
| 409 | The action conflicts with the current state (campaign is full, already applied...) | Show the message and refresh the data |
| 429 | Too many tries (`throttled`), or a cooldown (`resend_cooldown`, `refresh_cooldown`) | Show the message; the wait time is in it |
| 503 | `temporarily_unavailable`: a dependency is down | Offer "try again" |

The full list of codes is in section 9.

### 2.4 Lists and pages

List endpoints return:

```json
{ "count": 134, "next": "http://.../?page=2", "previous": null, "results": [ ... ] }
```

Use `?page=` and `?page_size=` (default 20, **maximum 50**). Asking for a page that does not exist returns
404. Use the `next` and `previous` links as given. Three lists add extra fields next to `results`:

- notifications add `unread_count` (the number for the bell badge, covering **all** unread, not just this page);
- the brand's proposal list adds `accepted_count` and `creators_needed` ("2 of 3 accepted");
- nothing else does.

### 2.5 Data formats

| Kind | Format |
|---|---|
| Dates and times | ISO 8601 with a time zone, for example `"2026-11-01T18:00:00Z"`. Always send a zone (`Z` or `+06:00`). Show them in the user's local time |
| Money (`budget`, `proposed_rate`, `rate_post`...) | **Strings** with 2 decimals, `"150.00"`. Never convert to a float for display or maths. Send strings back |
| Engagement rate (`engagement_rate`) | A **percentage** as a string, `"4.20"` means 4.2%. Allowed 0 to 100 |
| Rating average (`rating_avg`) | A string such as `"4.50"`, or `null` when the creator has no reviews |
| Acceptance rate (`acceptance_rate`) | A **number from 0 to 1** (0.5 means 50%), or `null` when nothing was sent. This one is a ratio, not a percentage |
| Missing image or link | `null`. Draw an initials avatar for a missing photo or logo |
| Images | The API stores **links only** (`photo_url`, `logo_url`). There is no upload endpoint. The frontend needs its own way to host images, or users paste links |
| Text | HTML is stripped by the backend; links must start with `http://` or `https://` (otherwise `invalid_url`) |

### 2.6 Limits

Rate limits are per IP address. Show a friendly message on 429.

| Action | Limit |
|---|---|
| Register | 5 per minute |
| Login | 10 per minute |
| Admin login | 5 per minute |
| Request password reset | 5 per hour |
| Confirm password reset | 10 per hour |
| Verify email code | 20 per hour |
| Resend verification code | 5 per hour, and at most one per minute |
| Finish YouTube connect | 20 per hour |

---

## 3. The picture in one minute

```
creator ── applies to ──► campaign ◄── posts ── brand
                │                            │
         proposal (status)            shortlist / accept / reject
                │                            │
                └──────── accepted ──────────┘
                              │
                 creator adds deliverable links
                              │
                  brand marks Completed (final)
                              │
                       brand leaves a review (1 to 5)
```

**Campaign status:** `draft` → `published` → `closed`. Only drafts can be edited or deleted. A closed
campaign never reopens. A published campaign closes by itself after its deadline (within 5 minutes), or when
the brand closes it.

**Proposal status:** `pending` → `shortlisted` → `accepted`, or `rejected`, or `withdrawn`.
Shortlist works only from `pending`. Accept and Reject work from `pending` or `shortlisted` and cannot be
undone. Pressing Accept twice is harmless. A creator can withdraw a live proposal; an accepted one needs a
reason. A rejected creator cannot apply to the same campaign again. A withdrawn creator can apply again while
the campaign is still published (that is a new entry in their list).

**The slot rule:** accepted proposals can never exceed the campaign's `creators_needed` (1 to 20), even when
many clicks arrive at the same moment. A campaign does **not** close itself when it is full.

---

## 4. Accounts and sign-in

### 4.1 Register

`POST /auth/register/` (no token)

```json
{ "role": "creator", "full_name": "Amina Rahman", "email": "amina@example.com",
  "username": "amina", "password": "at-least-8-chars", "mobile_number": "+8801712345678" }
```

- `role` is `creator` or `brand` (choose it first, before the other fields). Nobody can register as admin.
- Email and username must be unique, ignoring capital letters.
- Returns **201** with the user, but **no token**. Call login next.
- After registering, a 6-digit code is emailed (section 4.2).

The user object (also returned by `GET /auth/me/`):

```json
{ "id": 7, "full_name": "Amina Rahman", "email": "amina@example.com", "username": "amina",
  "role": "creator", "mobile_number": "+8801712345678", "email_verified": false }
```

### 4.2 Verify the email

- `POST /auth/email/verify/` `{ "code": "123456" }` (needs the token) returns the updated user.
- `POST /auth/email/resend/` sends a new code. Errors: `resend_cooldown` (429, wait a minute) and
  `already_verified` (409).
- Code errors (all 400): `invalid_verification_code`, `verification_code_expired` (10 minutes),
  `verification_code_used`, `verification_code_locked` (5 wrong tries; ask for a new code).

Verification does **not** block anything in the API. It decides whether notification emails are sent
(section 7.8). Show a gentle "verify your email" banner while `email_verified` is `false`.

### 4.3 Log in

`POST /auth/login/` (no token)

```json
{ "identifier": "amina@example.com", "password": "..." }
```

`identifier` is the email **or** the username. Returns:

```json
{ "access": "<token>", "user": { ...user object... } }
```

Wrong password, unknown user, suspended account and admin accounts all return the same 401
`invalid_credentials`. Send the person to the screens of their `user.role` after login.

### 4.4 Who am I, and log out

- `GET /auth/me/` returns the user object. Call it on app start to check the stored token still works.
- `POST /auth/logout/` returns 204 and ends **all** sessions of this person. Then delete the token locally.

### 4.5 Forgot password

1. `POST /auth/password-reset/request/` `{ "email": "..." }` always returns 200 with the same generic message,
   whether or not the account exists. Never say "no such account".
2. A 6-digit code is emailed (valid 10 minutes, works once, locked after 5 wrong tries).
3. `POST /auth/password-reset/confirm/` `{ "email": "...", "code": "123456", "new_password": "..." }` returns 200.
   Send the person to the login page; they are signed out everywhere.

Errors (400): `invalid_reset_code`, `reset_code_expired`, `reset_code_used`, `reset_code_locked`, and
`validation_error` for a weak password (the code is **not** used up in that case).

---

## 5. Creator app

### 5.1 Home (dashboard)

`GET /creators/me/dashboard/`

```json
{ "profile_completion": 62,
  "youtube": { "connected": true, "status": "connected", "needs_reconnect": false,
               "last_synced_at": "...", "is_outdated": false },
  "available_campaigns": [ ...5 newest open campaign cards... ],
  "applications": [ ...latest proposals... ],
  "accepted_campaigns": [ ...proposals that are accepted... ],
  "performance": { "proposals_sent": 8, "accepted": 3, "acceptance_rate": 0.375 } }
```

### 5.2 Profile

- `GET /creators/me/` and `PATCH /creators/me/` (send only the fields that changed).
- Editable: `full_name`, `photo_url`, `bio` (1000), `niche`, `primary_platform`, `city`, `country`,
  `rate_post`, `rate_story`, `rate_video`. Read only: `id`, `username`, `rating_avg`, `rating_count`,
  `completion_percent`, `stats`.
- `niche` is one of `fitness`, `tech`, `beauty`, `food`, `travel`, `other`. `primary_platform` and every
  `platform` is one of `instagram`, `youtube`, `tiktok`, `facebook`. Both can be `null` until chosen.
- `completion_percent` (0 to 100) drives the progress bar. It is made of 8 equal items: photo, bio, niche,
  main platform, city **and** country, at least one rate, numbers for the main platform, and at least one
  portfolio item. Use it to tell the creator what to fill in next.

### 5.3 Audience numbers ("stats")

- `GET /creators/me/stats/` returns one entry per platform:
  `{ platform, handle_url, followers, engagement_rate, is_verified, is_outdated, last_synced_at }`.
- `PUT /creators/me/stats/{platform}/` with `{ "followers": 12000, "engagement_rate": "4.20", "handle_url": "https://..." }`
  saves numbers typed by hand. These are labelled **Unverified** (`is_verified: false`). `{platform}` must be
  one of the four platforms (otherwise 404).
- Typing over numbers that came from a connected YouTube account is refused: **409 `stats_verified`**. Disable
  the form for those and show the Verified badge instead.
- **Verified** (connected account) vs **Unverified** (typed by hand) must always be visible.
- `is_outdated: true` means the connection broke and these are the last known numbers. Show a "reconnect"
  prompt.

### 5.4 Portfolio

- `GET /creators/me/portfolio/` returns a plain array (no paging). `POST` with `{ "url", "caption", "source" }`
  (`source` is `manual` or `youtube`). `DELETE /creators/me/portfolio/{id}/` returns 204.
- Maximum **10** items: the eleventh gets **409 `portfolio_full`**. Disable "Add" at 10.
- Suggest items from `GET /social/youtube/recent-content/` (section 8) and add the chosen one with
  `"source": "youtube"`.

### 5.5 Find campaigns

`GET /campaigns/` lists **open** campaigns only (published and before their deadline).

| Query parameter | Meaning |
|---|---|
| `q` | search in title and description |
| `niche`, `platform` | exact match |
| `min_budget`, `max_budget` | decimal strings |
| `deadline_after`, `deadline_before` | date-times |
| `page`, `page_size` | paging |

Each card: `{ id, title, brand: {id, name, logo_url}, niche, budget, platform, deadline, creators_needed, eligible }`.

`eligible` is a **hint only**: `true` when the creator has numbers for that platform and enough followers.
Show "You may not match" when `false`, but **never block** the Apply button because of it.

`GET /campaigns/{id}/` adds `description`, `deliverables`, `min_followers`, `status`, `accepted_count`,
`all_creators_selected`, `can_apply` and `apply_blocked_reason`.

- Draw the Apply button from **`can_apply`**. When it is `false`, `apply_blocked_reason` says why:
  - `active_proposal`: already applied (show "Applied", link to the proposal);
  - `proposal_rejected`: rejected earlier, can never re-apply;
  - `campaign_closed`: closed or past its deadline.
  When `can_apply` is `true`, the reason is `null`.
- `all_creators_selected: true` means every slot is taken. Show "All creators selected". Applying is still
  allowed by the server unless `can_apply` says otherwise.
- Closed campaigns still open (so "Apply is disabled" can be explained); drafts and other people's drafts are 404.
- Opening this page counts as a view for the brand's analytics.

### 5.6 Apply

`POST /campaigns/{id}/proposals/`

```json
{ "cover_message": "Hi! ...", "proposed_rate": "150.00",
  "portfolio_links": ["https://..."], "experience_note": "Optional" }
```

- `cover_message` up to 3000 characters, `proposed_rate` required, up to 3 `portfolio_links`,
  `experience_note` up to 2000.
- **201** returns the proposal. A proposal **cannot be edited** afterwards (only withdrawn).
- Errors (409): `campaign_closed`, `proposal_exists` (double click or already applied), `proposal_rejected`.
- Two clicks at once still create exactly one proposal. Disable the button while sending anyway.

### 5.7 My applications

- `GET /creators/me/proposals/` (optional `?status=`) newest first:
  `{ id, status, proposed_rate, created_at, completed_at, withdrawal_reason, campaign: {id, title, status, brand: {id, name}} }`.
  A re-application is a separate entry. Withdrawn ones stay as history.
- `POST /creators/me/proposals/{id}/withdraw/` with `{ "reason": "..." }` (up to 300 characters).
  The **reason is required when the proposal is accepted** (otherwise 400 `validation_error` on `reason`).
  Errors: `already_completed` (409, completed work cannot be withdrawn), `invalid_transition` (409).
  The brand is told a slot has opened.

### 5.8 Delivering the work (after being accepted)

- `GET /creators/me/proposals/{id}/deliverables/` returns an array.
- `POST` the same address with `{ "post_url": "https://...", "platform": "youtube", "note": "..." }`.
- `PATCH` / `DELETE /creators/me/proposals/{id}/deliverables/{deliverable_id}/` edit or remove one.
- Allowed only while the proposal is `accepted` and not yet completed. After that: **409 `deliverables_locked`**.
  Maximum 20 per proposal: **409 `deliverables_full`**.
- Once the brand marks it Completed, `completed_at` is set on the proposal: show it as final.

### 5.9 Brand profile (read only)

`GET /brands/{user_id}/` shows a brand's company profile to creators:
`{ id, display_name, company_name, industry, website, logo_url, about }`. The id is the brand's **user id**,
the same `brand.id` you get inside campaign cards.

---

## 6. Brand app

### 6.1 Home (dashboard)

`GET /brands/me/dashboard/` returns totals (`total_campaigns`, `active_campaigns`, `total_proposals`,
`shortlisted_count`, `accepted_count`) and `campaigns` (the 50 newest, each with `proposal_count`,
`accepted_count`, `creators_needed` and `proposals_url`).

> `proposals_url` (and `profile_url` on proposals) are **API paths** such as `/api/v1/brand/campaigns/12/proposals/`,
> not frontend routes. Take the id from them or use the ids already in the data; build your own page links.

### 6.2 Company profile

`GET /brands/me/` and `PATCH /brands/me/`: `company_name`, `industry`, `website`, `logo_url`, `about`.

### 6.3 Campaigns

- `GET /brand/campaigns/` (optional `?status=draft|published|closed`) lists the brand's own campaigns.
- `POST /brand/campaigns/` creates a **draft**:

  ```json
  { "title": "...", "description": "...", "niche": "fitness", "platform": "instagram",
    "budget": "500.00", "deadline": "2026-11-30T18:00:00Z", "deliverables": "2 posts and 3 stories",
    "creators_needed": 2, "min_followers": 5000 }
  ```
  `creators_needed` is 1 to 20 (default 1). `min_followers` is optional (`null` for none). `budget` is more
  than 0. The deadline must be in the future (400).
- `GET /brand/campaigns/{id}/`, `PATCH` and `DELETE` work **only while it is a draft**; otherwise
  **409 `campaign_not_editable`** (the check comes before field validation).
- `POST /brand/campaigns/{id}/publish/`: draft to published. Errors: `invalid_campaign_transition` (409),
  `deadline_in_past` (400, the deadline passed while it was a draft: let the brand edit it).
- `POST /brand/campaigns/{id}/close/` has no body. Closing is final. Closing a closed campaign is harmless.
- Other brands' campaigns are 404.

Disable buttons by status: Edit/Delete/Publish for `draft`, Close for `published`, nothing for `closed`.

### 6.4 Find creators

`GET /creators/` (brands only):

| Query parameter | Meaning |
|---|---|
| `q` | name or username |
| `niche`, `platform` | exact match |
| `min_followers`, `max_followers` | numbers, applied to the creator's **main** platform |
| `min_engagement`, `max_engagement` | percent strings |
| `min_rate`, `max_rate` | matches when any of the creator's three rates is in range |
| `min_rating` | minimum average rating |
| `location` | city or country |
| `verified_only` | `true` to show only Verified numbers |
| `ordering` | `followers`, `-followers` (default), `engagement`, `-engagement`, `rate`, `-rate`, `rating`, `-rating` |

A bad value returns 400 with the field named. Creators with no numbers still appear, at the bottom.

Card: `{ id, name, photo_url, niche, primary_platform, followers, engagement_rate, is_verified, rating_avg, rating_count }`.
`followers` and `engagement_rate` can be `null`.

`GET /creators/{user_id}/` returns the full profile (bio, location, three rates, all `stats`, `portfolio`,
rating). `GET /creators/{user_id}/reviews/` returns the reviews they received (paged, newest first).

### 6.5 Proposals for a campaign

`GET /brand/campaigns/{id}/proposals/` (optional `?status=`), newest first. **Withdrawn proposals are hidden**
unless you ask with `?status=withdrawn`. The envelope adds `accepted_count` and `creators_needed`.

Each item:

```json
{ "id": 31, "status": "pending", "proposed_rate": "150.00", "cover_message": "...",
  "portfolio_links": ["..."], "experience_note": "...", "withdrawal_reason": null,
  "completed_at": null, "created_at": "...", "profile_url": "/api/v1/creators/5/",
  "creator": { "id": 5, "name": "...", "niche": "fitness", "platform": "instagram", "followers": 12000,
               "engagement_rate": "4.20", "is_verified": true, "rating_avg": "4.50", "rating_count": 3 } }
```

**Buttons** (all are `POST`, no body, address `/brand/proposals/{id}/...`):

| Button | Address | Works from | Result |
|---|---|---|---|
| Shortlist | `shortlist/` | `pending` | status `shortlisted` |
| Accept | `accept/` | `pending`, `shortlisted` | status `accepted` |
| Reject | `reject/` | `pending`, `shortlisted` | status `rejected` |

Each returns `{ id, status, accepted_count, creators_needed }`. **Use that reply to update the counter** instead
of guessing. Errors (409): `campaign_full` (every slot taken: refresh the list), `invalid_transition`.
Accept and Reject cannot be undone, so confirm them in the UI. Clicking Accept twice is safe.

### 6.6 Completing and reviewing

1. After the creator delivers, `GET /brand/campaigns/{id}/deliverables/` shows, per accepted creator,
   `{ proposal_id, creator: {id, name}, completed_at, deliverables: [...] }`.
2. `POST /brand/proposals/{id}/complete/` (no body) returns `{ id, status, completed_at }`. It is **final**
   (no more deliverable changes, no withdrawing). No deliverable is required first. Repeating it is harmless.
3. `POST /brand/proposals/{id}/review/` with `{ "rating": 5, "text": "optional, up to 500" }` returns 201 with
   `{ id, rating, text, brand: {id, name, logo_url}, campaign: {id, title}, created_at }`.
   Errors (409): `not_completed` (complete it first), `already_reviewed`. One review per collaboration; no editing.

### 6.7 Analytics for a campaign

- `GET /brand/campaigns/{id}/analytics/`:

  ```json
  { "views": 120,
    "funnel": { "received": 14, "shortlisted": 4, "accepted": 2, "rejected": 3, "withdrawn": 1 },
    "accepted_vs_needed": { "accepted": 2, "needed": 3 },
    "avg_proposed_rate": "140.00", "budget_per_creator": "166.67", "acceptance_rate": 0.1429 }
  ```
  `avg_proposed_rate` and `acceptance_rate` are `null` when there is nothing to average.
  `acceptance_rate` is a ratio from 0 to 1.
- `GET /brand/campaigns/{id}/analytics/content/` returns one row per delivered post:
  `{ deliverable_id, proposal_id, creator, platform, post_url, views, likes, comments, engagement_rate, synced_at }`.
  Any figure can be the text **`"not_available"`** instead of a number (not synced yet, not a YouTube link, or
  the server has no key). Show a dash, never `0`. The numbers are a daily snapshot, so this call is fast and
  never waits for YouTube.

---

## 7. Everything shared

### 7.1 Notifications

- `GET /notifications/` (paged, newest first) returns the results plus **`unread_count`** for the badge.
- `POST /notifications/{id}/read/` marks one as read. `POST /notifications/read-all/` returns `{ "marked_read": 4 }`.
- Each item: `{ id, kind, message, payload, is_read, created_at }`. `message` is a ready-to-show sentence.
  `payload` holds ids for navigation:

| `kind` | For | `payload` | Suggested click target |
|---|---|---|---|
| `proposal_received` | brand | `campaign_id`, `proposal_id` | the campaign's proposal list |
| `proposal_withdrawn` | brand | `campaign_id`, `proposal_id` | the campaign's proposal list |
| `campaign_auto_closed` | brand | `campaign_id` | the campaign page |
| `proposal_shortlisted` | creator | `campaign_id`, `proposal_id` | my applications |
| `proposal_accepted` | creator | `campaign_id`, `proposal_id` | my applications |
| `proposal_rejected` | creator | `campaign_id`, `proposal_id` | my applications |
| `account_reconnect` | creator | `platform` | the connections page |

There is no push or live channel. Poll `GET /notifications/` (for example when the app gets focus or every
minute) to refresh the badge.

### 7.2 Notification emails on or off

`GET /settings/notifications/` returns `{ "email_enabled": true, "email_verified": false }`.
`PATCH` with `{ "email_enabled": false }` turns notification emails off. Reset and verification codes are
**always** sent. Notification emails are sent only when the email is verified **and** `email_enabled` is true.

---

## 8. Connecting YouTube (creators)

A creator can connect a YouTube channel so the follower count and engagement rate become **Verified** and
refresh daily. The connection is read-only and the tokens never leave the server.

### The flow (three steps, and the frontend owns steps 2 and 3)

```
1. Creator clicks "Connect YouTube"
   frontend ──GET /social/youtube/connect/──► { "authorization_url": "https://accounts.google.com/..." }
   frontend sends the browser to authorization_url  (window.location = url)

2. Google shows its consent screen, then sends the browser to the BACKEND callback.
   The backend checks it and redirects the browser to YOUR page:
   FRONTEND_URL/settings/connections?youtube=confirm&code=...&state=...
   or on a problem:
   FRONTEND_URL/settings/connections?youtube=error&reason=access_denied|invalid_state|...

3. Your page (the creator is logged in) reads code and state from the address and sends them back UNCHANGED:
   frontend ──POST /social/youtube/complete/  { "state": "...", "code": "..." }──► YouTube status (200)
   then removes code/state from the address bar.
```

Why step 3 exists: it proves the person finishing the connection is the one who started it. A link started by
someone else is refused with **400 `invalid_state`**.

**Build the page `/settings/connections` to handle these cases:**

| Address has | Do |
|---|---|
| `youtube=confirm` | Call `complete` with `code` and `state`, show a spinner, then show the result |
| `youtube=error&reason=access_denied` | The creator pressed Cancel at Google. Show "Connection cancelled" |
| `youtube=error&reason=invalid_state` | The link expired (10 minutes) or is invalid. Offer "Try again" |

`complete` errors: `invalid_state` (400, start again), `exchange_failed` (400, Google refused, try again),
`no_refresh_token` (400, the creator must accept every permission on the consent screen), `throttled` (429),
`temporarily_unavailable` (503, try again). It is safe to retry after a 503.

**Connection status:** `GET /social/youtube/`

```json
{ "connected": true, "status": "connected", "needs_reconnect": false, "connected_at": "...",
  "last_synced_at": "...", "is_outdated": false, "last_error": null }
```

- `status` is `connected`, `needs_reconnect` or `null` (never connected).
- The first sync runs in the background right after connecting: the numbers appear a few seconds later.
  Refetch `GET /social/youtube/` and `GET /creators/me/stats/` after a short delay.
- When `needs_reconnect` is `true`, show a "Reconnect YouTube" button that starts step 1 again. The last
  numbers stay visible and `is_outdated` is `true`. While the Google app is in Testing mode, this happens
  about every **7 days**. That is normal.
- `last_error` can be `"no_channel"` (the Google account has no YouTube channel) or `"token_revoked"`.

**Other calls:**

| Call | Result |
|---|---|
| `POST /social/youtube/refresh/` | **202**, a refresh is queued. Errors: `refresh_cooldown` (429, once every 15 minutes), `reconnect_required` (409), 404 if not connected |
| `DELETE /social/youtube/` | 204. Tokens are deleted. The numbers stay but become Unverified |
| `GET /social/youtube/recent-content/` | Array of `{ video_id, title, url, published_at }` for suggesting portfolio items |

---

## 9. Admin screens

Log in at `POST /admin/auth/login/` (same body as the normal login). Admin accounts are created on the server
and cannot register.

| Screen | Call |
|---|---|
| Overview numbers | `GET /admin/overview/` returns `users {total, suspended, by_role}`, `signups` (per day, last 30 days), `campaigns_by_status`, `total_proposals` |
| Users | `GET /admin/users/` with `?q=`, `?role=creator|brand|admin`, `?status=active|suspended` |
| Suspend / reactivate | `POST /admin/users/{id}/suspend/` and `.../reactivate/` with `{ "reason": "..." }` |
| Delete a user | `DELETE /admin/users/{id}/` **with a JSON body** `{ "reason": "..." }` and `Content-Type: application/json` |
| Close a campaign | `POST /admin/campaigns/{id}/close/` with `{ "reason": "..." }` |
| Remove a review | `DELETE /admin/reviews/{id}/` **with a JSON body** `{ "reason": "..." }` |
| Audit trail | `GET /admin/actions/` (newest first) |

- `reason` is **required** on every action (up to 500 characters).
- Make sure your HTTP client sends the body on `DELETE`. Some wrappers drop it, and the call then fails with
  `validation_error`.
- Errors (409): `cannot_modify_self` (admins cannot suspend or delete themselves), `already_suspended`,
  `already_active`.
- Suspending a person signs them out everywhere and blocks login. Their campaigns and proposals **stay
  visible** to others (a known gap).

---

## 10. Pages and routes the backend assumes

The backend is fixed on these. **Create them, or tell the backend developer your real routes** (the email
links live in one dictionary in `apps/notifications/emails.py`).

| Route | Used by |
|---|---|
| `/settings/connections` | The YouTube redirect from Google (section 8), and the "reconnect" email button |
| `/creator/applications` | Email button for creators: proposal shortlisted, accepted, rejected |
| `/brand/campaigns/{id}/proposals` | Email button for brands: new proposal, proposal withdrawn |
| `/brand/campaigns/{id}` | Email button for brands: campaign closed automatically |
| `/settings/notifications` | Footer link of every notification email ("change email settings") |
| **Privacy Policy** and **Terms of Service** pages | Google requires both for the YouTube connection. These are frontend work |

---

## 11. Error codes you may see

| `code` | HTTP | Where | Meaning |
|---|---|---|---|
| `validation_error` | 400 | any form | `details` has the field messages |
| `invalid_url` | 400 | links | not an `http(s)` link |
| `role_not_allowed` | 400 | register | tried to register as admin |
| `invalid_credentials` | 401 | login | wrong login, suspended account, or wrong login page for the role |
| `not_authenticated` / `token_not_valid` | 401 | any | missing, expired or cancelled token |
| `permission_denied` | 403 | any | wrong role |
| `not_found` | 404 | any | missing, not yours, or not visible |
| `throttled` | 429 | limited calls | too many tries |
| `temporarily_unavailable` | 503 | YouTube connect | try again |
| `invalid_reset_code`, `reset_code_expired`, `reset_code_used`, `reset_code_locked` | 400 | password reset | code problems |
| `invalid_verification_code`, `verification_code_expired`, `verification_code_used`, `verification_code_locked` | 400 | email verify | code problems |
| `resend_cooldown` | 429 | resend code | wait a minute |
| `already_verified` | 409 | verify / resend | nothing to do |
| `campaign_not_editable` | 409 | edit / delete campaign | not a draft |
| `invalid_campaign_transition` | 409 | publish / close | wrong current status |
| `deadline_in_past` | 400 | publish | deadline has passed |
| `campaign_closed` | 409 | apply | closed or past deadline |
| `proposal_exists` | 409 | apply | already applied |
| `proposal_rejected` | 409 | apply | rejected before |
| `invalid_transition` | 409 | proposal buttons, withdraw | not allowed from this status |
| `campaign_full` | 409 | accept | all slots taken |
| `already_completed` | 409 | withdraw | completed work is final |
| `deliverables_locked`, `deliverables_full` | 409 | deliverables | not accepted yet or already completed / 20 max |
| `not_completed`, `already_reviewed` | 409 | review | complete first / one review only |
| `portfolio_full` | 409 | portfolio | 10 max |
| `stats_verified` | 409 | manual stats | numbers come from YouTube |
| `refresh_cooldown` | 429 | YouTube refresh | once every 15 minutes |
| `reconnect_required` | 409 | YouTube refresh | connection expired |
| `invalid_state`, `exchange_failed`, `no_refresh_token` | 400 | YouTube complete | see section 8 |
| `cannot_modify_self`, `already_suspended`, `already_active` | 409 | admin | see section 9 |

---

## 12. Mistakes to avoid

- Don't convert money strings to floats. Don't show `0` for `null` or `"not_available"`.
- Don't block Apply because `eligible` is `false`. Use `can_apply`.
- Don't count accepted creators yourself. Use `accepted_count` / `creators_needed` from the server.
- Don't cache the token past a 401, and don't try to refresh it. There is no refresh.
- Don't treat `acceptance_rate` as a percentage (it is 0 to 1) or `engagement_rate` as a ratio (it is a percentage).
- Don't send `code` and `state` anywhere except `POST /social/youtube/complete/`, and send them unchanged.
- Don't put `proposals_url` or `profile_url` in links; they are API paths.
- Don't assume a missing photo is an empty string. It is `null`.
- Always disable action buttons while a call is running, then update the screen from the reply.

---

## 13. A full test route

When everything is connected, walk through this once. If every step works, the main product works.

1. Register a brand and a creator. Check both emails arrive and the codes verify.
2. Creator: fill the profile, connect YouTube (or type numbers by hand), add a portfolio link.
3. Brand: create a campaign, publish it.
4. Creator: find it (check the "eligible" hint), open it, apply.
5. Brand: open the proposals, shortlist, then accept. Click Accept twice: the counter must go up once.
6. Creator: see the status change and the notification.
7. Creator: add deliverable links. Brand: mark Completed, then leave a review.
8. Brand: check the creator's rating in the directory and the campaign analytics.
9. Admin: log in, look at the overview, suspend a test user and check they cannot log in.

---

## 14. Who to ask

If a field is missing, a rule seems wrong or a response does not match this guide, tell the backend
developer. The reasons behind the rules are in `docs/DECISIONS.md`. When an endpoint changes, regenerate
your types from `docs/openapi.yml`.
