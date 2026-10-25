# Micro-Influencers' Platform

| | |
|---|---|
| **Project** | 4 - Micro-Influencers' Platform: two-sided creator / brand marketplace |
| **Team** | 8 members (Backend team no 1, Frontend team no 4) |
| **Timeline** | Sep 24 – Oct 23, 2026   |
| **Type** | Internship project |
| **Document** | Product Requirements Document |

---

## Table of Contents

1. Project Overview
   - 1.1 User Roles
   - 1.2 How the Requirements Map to the Brief
   - 1.3 User Flows
2. Scope Decisions
   - 2.1 Decisions That Apply to the Whole Project
   - 2.2 Extension Order
3. Functional Requirements
   - 3.1 Authentication & Access (Core): FR-01, FR-02
   - 3.2 Profiles, Social Accounts & Discovery (Core): FR-03 to FR-08
   - 3.3 Campaigns (Core): FR-09 to FR-12
   - 3.4 Proposals (Core): FR-13 to FR-16
   - 3.5 Dashboards & Notifications (Core): FR-17 to FR-19
   - 3.6 Extensions (Build Only After the Core Is Stable): FR-20 to FR-24
4. Non-Functional Requirements
   - 4.1 Performance
   - 4.2 Security
   - 4.3 Reliability & Integration
   - 4.4 Privacy & Compliance
   - 4.5 Usability
   - 4.6 Code Quality & Documentation
5. Risks & Dependencies
6. Suggested Delivery Phasing
7. Out of Scope (Phase 2)

---

## 1. Project Overview

A two-sided marketplace connecting micro-influencers (creators with roughly 1K–100K followers) with small-to-medium brands. Creators build profiles with audience stats and rates, and apply to brand campaigns. Brands discover creators, post campaigns and manage the proposals they receive.

**Core scope (from the project brief):** creator profile pages with audience stats and rates, campaign posting by brands, and an application / proposal submission flow.

**Key deliverables:** a discovery directory with filtering, a brand campaign dashboard, and a lightweight proposal management view.

**Why this matters:** Micro-influencers struggle to prove real audience numbers to brands and often lose deals to bigger names despite better engagement. Brands struggle to find the right niche creators and end up managing outreach through scattered DMs and spreadsheets. This platform solves both: verified stats give creators credibility, and structured discovery plus a proposal pipeline let brands find and manage the right creators in one place.

**Success criteria:** a brand can find and shortlist a relevant creator in a few minutes using the directory filters, a creator can apply to a matching campaign without leaving the platform, and every proposal has a clear status at every stage, with no lost or ambiguous applications.

### 1.1 User Roles

| Role | Description | Pain Point | Main goals |
|---|---|---|---|
| Creator | Micro-influencer with a niche audience | Hard to prove real audience numbers to brands; often overlooked in favor of bigger names despite good engagement | Build a profile with real stats, find suitable campaigns, apply, track application status |
| Brand | Small or medium business running influencer campaigns | Hard to find the right niche creators; tracking outreach and proposals manually across DMs/spreadsheets doesn't scale | Find the right creators, post campaigns, review and act on proposals |
| Admin | Platform administrator (extension only, see FR-22) | No way to catch bad actors or bad content without manual oversight | Manage users and moderate content |

### 1.2 How the Requirements Map to the Brief

- **Discovery directory with filtering:** FR-07, FR-08 (brands), FR-11, FR-12 (creators)
- **Brand campaign dashboard:** FR-09, FR-10, FR-18
- **Lightweight proposal management view:** FR-13 to FR-16
- **Creator profile pages with audience stats and rates:** FR-03, FR-05, FR-06

### 1.3 User Flows

**Creator flow**

1. Register and select the Creator role
2. Log in, land on the Creator Dashboard
3. Connect YouTube (or skip and enter stats manually)
4. Build profile: bio, niche, rates, portfolio
5. Browse the campaign directory, filter by niche/platform/budget
6. Open a campaign, check eligibility, submit a proposal
7. Track status on the dashboard (Pending → Shortlisted/Rejected/Accepted)
8. If Accepted: submit deliverables and await completion (FR-20, extension)

**Brand flow**

1. Register and select the Brand role
2. Log in, land on the Brand Dashboard
3. Build company profile
4. Create a campaign (Draft), then Publish it
5. Browse the creator directory, or wait for proposals to arrive
6. Review proposals per campaign: Shortlist, Accept or Reject
7. Track accepted count against Creators Needed
8. If built: mark collaborations Completed and leave a review (FR-20, FR-21)

---

## 2. Scope Decisions

Requirements are split into **Core** (mandatory, FR-01 to FR-19) and **Extensions** (FR-20 to FR-24, built only after the core is stable, in the order set in section 2.2). Anything not finished is moved to Phase 2.

### 2.1 Decisions That Apply to the Whole Project

- **Roles at launch:** Creator and Brand. Admin is an extension.
- **Authentication:** JWT-based sessions.
- **Social accounts:** YouTube connects through OAuth 2.0 and stats are pulled automatically. Instagram, TikTok and Facebook use manual entry, labelled Unverified. This is because Instagram and Facebook (both under Meta) require a Business or Creator account and Meta's app review, which can take weeks for a new, unverified app; TikTok has a separate developer approval process with similar delays, and without it API access is limited to a sandbox not usable by real users. YouTube is the only platform where real OAuth integration is realistic within the timeline. It may require Google's app verification for public use. Until then the app runs in Testing mode with registered test users, and manual entry is the fallback. In Testing mode, Google expires refresh tokens after 7 days, so creators may need to reconnect about once a week. This is expected and is handled by the reconnect notification and the outdated label in FR-05. The OAuth structure is built so these other platforms can be added once approved.
- **Notifications:** in-app (badge and dropdown). If FR-24 is built, the same events are also emailed to verified addresses, and users can turn this off. Email is also used for password reset (core) and for verification codes (FR-24 only). No push notifications, digests or marketing emails.
- **Portfolio:** external URL links only. No direct file or media uploads.
- **Proposal flow:** lightweight: status updates only, no in-platform messaging or negotiation.

### 2.2 Extension Order

1. **1st:** email notifications and email verification (FR-24), then collaboration completion, deliverables and creator ratings & reviews (FR-20, FR-21)
2. **2nd:** admin panel (FR-22)
3. **3rd:** campaign performance analytics (FR-23)

Password reset email is core (FR-02) and is not part of FR-24.

---

## 3. Functional Requirements

### 3.1 Authentication & Access (Core)

#### FR-01: User Registration & Role Selection

Users register by choosing a role (Creator or Brand) before entering their details.

- Required fields: Full Name, Email (unique), Username (unique), Password (minimum 8 characters), Mobile Number
- The role is fixed at registration and cannot be changed later

#### FR-02: Login, Routing & Password Reset

Login is shared, but routing is role-aware. After a successful login:

- Creators go to the Creator Dashboard and Brands go to the Brand Dashboard.
- Invalid credentials return a clear error message.
- Sessions use JWT, and users can log out at any time.

**Password reset:**

- The login page has a "Forgot password" link. The user enters their registered email and receives a 6-digit code.
- The code expires after 10 minutes, works once, and becomes invalid after 5 wrong attempts.
- The user enters the code and a new password (minimum 8 characters). After a reset, existing sessions are logged out (backend note: a JWT cannot be revoked on its own, so store a token version on the user and reject tokens with an older version).
- The response is the same whether or not the email is registered: "If this email is registered, a code has been sent."
- The code is emailed through the platform's transactional email service, which is part of the core, in a background job, so the request does not wait on the provider. If sending fails, the failure is logged and the user still sees the same message. They can request a new code (rate limited, see 4.2). If FR-24 is built, the same service also sends verification codes and notification emails.

Login does not require a verified email.

**Acceptance criteria**

- Correct code within 10 minutes: the password changes and the old one stops working.
- Expired or used code: rejected with a clear message.
- Unregistered email: same message, and no email is sent.
- Email provider down: the same message is shown, the failure is logged, and the user can request a new code later.

### 3.2 Profiles, Social Accounts & Discovery (Core)

#### FR-03: Creator Profile Management

Creators create and update their creator profile, which is visible to logged-in brands.

- Full Name and Profile Photo (URL)
- If no profile photo is set, or the link fails to load, an initials avatar is shown (first letter of the name on a colored background). The backend returns null when there is no photo.
- Bio / About
- Niche / Category (e.g. Fitness, Tech, Beauty, Food, Travel)
- Primary Platform (Instagram / YouTube / TikTok / Facebook)
- Location (City, Country)
- Rate per Post, Rate per Story, Rate per Video
- Followers and Engagement Rate: filled automatically from a connected account (FR-05); editable manually otherwise and then labelled Unverified
- A profile completion indicator shows how much of the profile is filled in

#### FR-04: Brand Profile Management

Brands create and update their company profile, which is shown on their campaigns.

- Company Name, Industry, Website, Logo (URL), About
- If no logo is set, or the link fails to load, an initials avatar is shown, the same as for creators.
- Brand profiles are visible to logged-in creators.

#### FR-05: Social Media Account Connection

Creators connect their YouTube account using OAuth 2.0. This is the primary way creator stats are populated.

**Data pulled automatically (where the API allows):**

- Channel handle / URL
- Subscriber count
- Engagement rate, calculated from recent videos
- Recent content (used to suggest portfolio items)

**Behaviour:**

- Only read-only, minimum-necessary permissions are requested, after a clear consent screen
- Connected accounts display a Verified badge
- Creators can disconnect at any time; disconnecting deletes the stored tokens
- Stats sync on connection, then refresh automatically once a day; creators can also refresh manually (with a cooldown)
- The last-synced time is shown next to every stat
- If a token expires or is revoked, the creator is notified to reconnect and the last known stats stay visible, marked as outdated

**Fallback:**

- For Instagram, TikTok and Facebook, and for YouTube if API access fails or is not yet approved, creators enter stats manually, labelled Unverified

#### FR-06: Portfolio Management

Creators maintain a portfolio of previous work for brands to review.

- Add items as external URLs (Instagram post, YouTube video, etc.) with a short caption
- Optionally pick an item from recent content pulled from the connected account
- Remove any item at any time; maximum of 10 items per creator

#### FR-07: Creator Discovery & Search (Brand-facing)

Logged-in Brands browse and filter all creator profiles in a discovery directory. The directory and every profile behind it require authentication, with no public or logged-out access.

- Search and filters: keyword (name or username), Niche / Category, Primary Platform, follower range, engagement rate range, Location, Rate range, Verified accounts only
- Results can be sorted by followers, engagement or rate, and are paginated
- Each result shows name, photo, niche, platform, followers, engagement rate and Verified badge
- If ratings are built (FR-21), a minimum-rating filter, rating sort and average rating are added

#### FR-08: Creator Profile View

Logged-in Brands open any creator from the directory to see the full profile. Viewing a profile requires authentication, so it is not accessible to logged-out visitors.

- Bio, niche and location
- Platform stats with Verified badge and last-synced time
- Rate card (per post / story / video)
- Portfolio items
- Ratings and reviews, if FR-21 is built

### 3.3 Campaigns (Core)

#### FR-09: Campaign Creation (Brand)

Brands create campaigns that work as job listings for creators. Campaigns are saved as Draft by default.

- Campaign Title, Description, Category / Niche target
- Required Platform, Budget (per creator), Application Deadline
- Deliverables per creator (e.g. "2 Instagram posts, 1 reel")
- Creators Needed: the number of creators the brand will choose for this campaign (required, whole number from 1 to 20, default 1)
- Minimum follower requirement (optional)

#### FR-10: Campaign Publishing & Management (Brand)

Brands manage the campaign lifecycle: **Draft → Published → Closed**.

- **Draft:** the brand can edit everything or delete it
- **Published:** visible to creators (only published campaigns are visible). It cannot be edited or deleted, only closed
- **Closed:** the brand can close a campaign at any time, and it closes automatically when the Application Deadline passes. A closed campaign cannot be reopened
- The campaign does not close automatically when the brand has accepted all the creators it needs (Creators Needed)
- Closing stops new applications. The brand can still review and respond to proposals it has already received

#### FR-11: Campaign Discovery (Creator-facing)

Logged-in Creators browse published campaigns and filter them using the options below. The directory requires authentication, with no public or logged-out access.

- Filters: Category / Niche, Platform, Budget range, Application Deadline, and keyword search
- Each campaign card shows Title, Brand name, Category, Budget (per creator), Platform, Application Deadline and Creators Needed, plus an eligibility indicator based on the campaign's platform and minimum follower requirement.
- Eligible = the creator has stats for the campaign's required platform and followers meet the minimum (if set). Unverified stats count; the indicator is informational and does not block applying.

#### FR-12: Campaign Detail View

Logged-in Creators open a published campaign to see full details before applying. Viewing a campaign requires authentication.

- Brand name (linked to the brand profile), title and description
- Required platform, deliverables per creator, budget (per creator), Application Deadline, Creators Needed and minimum follower requirement
- "Brand has selected all creators" is shown when the number of accepted creators equals Creators Needed
- The Apply button is disabled if the creator has an active or rejected proposal, or the campaign is closed. It becomes enabled again after a withdrawal, only while the campaign is Published.

### 3.4 Proposals (Core)

#### FR-13: Proposal Submission (Creator)

Creators apply to published campaigns by submitting a proposal.

- Fields: cover message, proposed rate, portfolio links (up to 3, pre-filled from the profile if available), relevant experience note
- Only one active proposal (Pending, Shortlisted or Accepted) is allowed per campaign
- Proposals cannot be edited
- A creator can withdraw while the proposal is Pending, Shortlisted, or Accepted, whether the campaign is Published or Closed. Withdrawing an Accepted proposal needs a short reason (up to 300 characters). A Rejected proposal cannot be withdrawn. After withdrawing, the creator can resubmit only if the campaign is still Published.
- A Rejected proposal cannot be resubmitted

#### FR-14: Proposal Management (Brand)

Brands view all proposals received for each of their campaigns.

**Each proposal shows:**

- Creator name, niche and platform
- Follower count, engagement rate, proposed rate and cover message
- Portfolio links and relevant experience note
- Status (Pending, Shortlisted, Accepted, Rejected or Withdrawn). If the creator withdrew after being accepted, their reason is shown.
- Link to the creator's full profile

**The proposal list:**

- Shows how many creators have been accepted out of Creators Needed (e.g. "2 of 3 creators accepted"). The count includes only proposals that are currently Accepted.
- Is sorted newest first and can be filtered by status
- Hides Withdrawn proposals by default. They appear when the status filter is set to Withdrawn

#### FR-15: Proposal Status Management (Brand)

Brands act on each proposal, and the creator is notified each time:

- **Shortlist:** mark as a strong candidate
- **Accept:** confirm the creator for the campaign
- **Reject:** decline the proposal

**Rules:**

- A Pending proposal can be shortlisted, accepted or rejected. A Shortlisted one can be accepted or rejected
- The brand cannot undo an Accept or a Reject. An Accepted proposal changes only if the creator withdraws it (FR-13). This frees the slot, and the brand can accept another proposal, even after the campaign closes.
- Accepted proposals must never exceed Creators Needed, even if several Accept requests arrive at the same time. When the campaign is full, Accept is blocked with the message "All creators for this campaign have already been selected." Shortlist and Reject still work.
- Accept on a proposal that is already Accepted changes nothing and shows no error.
- Withdrawn proposals cannot be acted on
- These actions remain available after the campaign closes

**Acceptance criteria**

- Two simultaneous Accepts on the last slot: exactly one succeeds and the other gets the error.
- Full campaign: Accept is blocked, but Shortlist and Reject still work.
- Full campaign, then an Accepted creator withdraws: the count drops by 1 and Accept works again.
- Double-click Accept on the same proposal: it is Accepted once, the count goes up by 1, and there is no error.

#### FR-16: Application Status Tracking (Creator)

Creators see every campaign they applied to and the status of each proposal:

- Statuses: Pending, Shortlisted, Accepted, Rejected, Withdrawn
- Shown as a simple status list, status only, no messaging or negotiation
- Withdrawn proposals stay in the list as history. A resubmission appears as a new entry.

### 3.5 Dashboards & Notifications (Core)

#### FR-17: Creator Dashboard

The creator's home after login. It shows:

- Profile completion indicator
- Connected account with last-synced status and reconnect prompt
- Available campaigns (latest 5, with a link to full discovery)
- My Applications with statuses
- Accepted campaigns, highlighted separately
- Performance summary: proposals sent and acceptance rate (proposals currently Accepted ÷ proposals sent). Withdrawn proposals count as sent. A proposal that was Accepted and then withdrawn does not count as accepted.

#### FR-18: Brand Dashboard

The brand's home after login. It shows:

- Total campaigns and active (published) campaigns
- Total proposals received across all campaigns (withdrawn ones included)
- Shortlisted and accepted creators count (only proposals currently in that status)
- Quick links to each campaign's proposal list

#### FR-19: Notification System (In-App)

Notifications are created in-app first. Email delivery is handled by FR-24 if built. No push.

**Creators are notified when:**

- Their proposal is Shortlisted, Accepted or Rejected
- A connected account needs to be reconnected

**Brands are notified when:**

- A new proposal is submitted to one of their campaigns
- A creator withdraws a proposal at any stage. If it was Accepted, the notification says a slot has opened.
- A campaign closes automatically at its Application Deadline

A count badge sits on the nav bar. Clicking it opens a dropdown of recent notifications. Notifications are marked as read when clicked, and users can mark all as read.

### 3.6 Extensions (Build Only After the Core Is Stable)

These are numbered FR-20 to FR-24. The build order is set in section 2.2 and does not follow the numbering. Extension notifications and dashboard items are added only when the related extension is built.

#### FR-20: Collaboration Completion & Deliverables

For each accepted proposal, the creator submits deliverables and the brand marks that collaboration as Completed.

- Creator submits links to the published content (post URL, platform, optional note) and can update them until completion
- Brand views each creator's deliverables from the campaign page
- Completion is tracked separately for each accepted creator. The campaign can have some creators completed and others not
- Only Accepted proposals can be marked Completed. Completion is final and unlocks the review (FR-21)

#### FR-21: Creator Ratings & Reviews

After a collaboration is completed, the brand can rate and review the creator.

- Rating from 1 to 5 stars, with an optional written review (up to 500 characters)
- One review per completed collaboration; only the brand that ran the campaign can review; reviews cannot be edited
- Average rating and review count are recalculated automatically and shown on the creator profile, discovery cards and proposal view

#### FR-22: Admin Panel

Admin accounts are created by a seed script, not public registration. Admins log in to a separate Admin Panel.

- **User management:** view, search and filter users; suspend and reactivate accounts (suspended users cannot log in); delete with confirmation; admins cannot suspend or delete themselves
- **Content moderation:** close campaigns, remove inappropriate reviews (ratings recalculated); every action records admin, target, reason and timestamp
- **Platform overview:** total users and sign-ups over time, campaigns by status, total proposals

#### FR-23: Campaign Performance Analytics (Brand)

Brands view analytics for each campaign, built in this order:

- **Proposal metrics (first):** campaign views, proposal funnel (received, shortlisted, accepted, rejected, withdrawn), accepted vs Creators Needed, average proposed rate vs budget per creator, and acceptance rate. Acceptance rate is proposals currently Accepted ÷ proposals received. Withdrawn proposals count as received, and a proposal that was Accepted and then withdrawn does not count as accepted.
- **Content performance (last, first to be cut):** views, likes, comments and engagement rate per deliverable; shows "not available" where the API does not provide the data

#### FR-24: Email Notifications & Email Verification

This extension reuses the email service set up for password reset (FR-02). It adds notification emails, email verification, the Notification Settings toggle, and retry with backoff.

**Verification:** after registration a 6-digit code is emailed (same rules as the reset code: 10 minutes, single use, 5 wrong attempts). Resend has a 60-second cooldown. Users can log in unverified, but only verified emails receive notification emails.

**Notification emails:** a second channel for existing FR-19 events only. No new events.

- Creators: proposal Shortlisted, Accepted or Rejected; account needs reconnecting (once per token failure, not daily)
- Brands: new proposal; creator withdrew (if Accepted, says a slot opened); campaign auto-closed

Each email has a subject naming the event, a short body, and one button linking to the page in the app (login required). No rates, proposal text or stats in the body. The footer links to Notification Settings.

**Suspended users** (FR-22) get no emails.

**Notification Settings:** one on/off toggle, default On. Reset and verification codes are always sent.

**Delivery:** queued and sent in the background, retried with backoff, failures logged. An email failure never blocks the request or removes the in-app notification.

**Acceptance criteria**

- Proposal accepted, toggle on, email verified: in-app notification plus email.
- Toggle off or email unverified: in-app only.
- Email provider down: in-app works, email retries, the user sees no error.

---

## 4. Non-Functional Requirements

### 4.1 Performance

- List and directory pages load within 3 seconds
- Filters and search apply without a full page reload; long lists are paginated
- Calls to third-party APIs run in the background and never block page loading

### 4.2 Security

- Passwords are stored using a salted, slow password hash (Django's default hasher). Plain-text passwords are never stored or logged.
- JWT tokens expire after 24 hours; all protected routes require a valid token
- Protected routes include the discovery directory and every profile/campaign view, not only dashboards and management pages. Per FR-07, FR-08, FR-11 and FR-12, these require login too
- Role-based access control: users can modify only their own data
- OAuth tokens are encrypted at rest and never sent to the frontend
- OAuth flows use a state parameter to prevent CSRF and request read-only, minimum-necessary scopes
- All input is validated and sanitised on the server (XSS and injection protection)
- Rate limiting on login, registration and password-reset endpoints; HTTPS in deployment
- Reset codes are stored hashed, expire, and are single-use.
- Email links never contain login tokens. Verification resend and email sends are rate limited.

### 4.3 Reliability & Integration

- A failure or rate limit from a social platform API must not break the platform
- Cached stats are shown with a last-synced time when a live fetch fails
- Failed API calls are retried with backoff; expired or revoked tokens are handled gracefully
- Creators Needed (1 to 20) is enforced by a database check constraint. The "accepted ≤ Creators Needed" rule is enforced on the server inside a database transaction with a row lock on the campaign, and verified by a concurrency test.
- Email provider failure must not affect any in-app feature.

### 4.4 Privacy & Compliance

- Privacy Policy and Terms pages are available (also required for social platform app review)
- Creators give explicit consent before connecting an account and can disconnect and delete stored tokens at any time
- Only the data needed for platform features is collected
- Notification emails can be disabled by the user. The Privacy Policy states which emails are sent.

### 4.5 Usability

- Fully responsive on mobile and desktop
- Consistent UI across the Creator and Brand areas
- Empty, loading and error states for every list and data view; form validation with clear error messages
- Images that are missing or fail to load (profile photos, logos) fall back to an initials avatar everywhere they appear, including discovery cards, profile views and proposal lists.

### 4.6 Code Quality & Documentation

- Frontend and backend repositories are kept separate, with a feature-branch and pull-request workflow
- API documented with Swagger or a Postman collection, agreed by both teams in week 1
- Environment variables for all secrets; no hardcoded credentials
- README with setup instructions in each repository
- Research, planning, decisions and iterations are documented throughout, as required by the project brief

---

## 5. Risks & Dependencies

| Risk | Impact | Mitigation |
|---|---|---|
| OAuth app approvals (Google, Meta, TikTok) can take days to weeks | Live account connection blocked for Instagram/Facebook (Business/Creator account + Meta review required) and TikTok (separate approval needed); this is why only YouTube is in core scope. | Register developer apps in week 1, use test users, keep the manual fallback, build YouTube first |
| Instagram data is limited to Business / Creator accounts | Personal accounts cannot be connected | Show guidance during connection and document the limitation |
| Some API metrics are not available on every platform | Some stats fields empty | Display only what is available; show "not available" otherwise |
| Large scope for a 23 Oct deadline | Delivery slips | Finish the core first; extensions follow the set order and are cut from the bottom |
| Third-party API rate limits | Stale or missing stats | Cache results and use scheduled syncs |
| Frontend and backend drift apart | Integration problems late in the project | Agree the API contract in week 1; use mock data until endpoints are ready |
| Email deliverability and provider limits | Emails land in spam or hit a daily cap, so reset codes (core) and notifications are missed | Set up the provider and verified sender domain (SPF/DKIM) early, because password reset in the core depends on it; test with real Gmail and Outlook inboxes; in-app stays the source of truth for notifications (reset codes have no in-app fallback, so test them first) |

---

## 6. Suggested Delivery Phasing

| Week | Backend (4 members) | Frontend (4 members) |
|---|---|---|
| **Week 1** (Sep 28 – Oct 2) | • Finalize PRD, system design and task breakdown together with frontend<br>• Database setup, authentication and roles, password reset, and email service setup (provider, sender domain)<br>• Register OAuth developer apps<br>• Draft the API contract | • Project setup, layout and shared components<br>• Login, registration and forgot-password / reset pages<br>• Dashboard shells<br>• Agree the API contract |
| **Week 2** (Oct 5 – Oct 9) | • Profile, campaign and proposal APIs<br>• YouTube OAuth and daily sync job | • Creator and brand profile pages<br>• Campaign create / manage pages<br>• Campaign list and detail pages<br>• Discovery directory |
| **Week 3** (Oct 12 – Oct 16) | • Discovery filters and sorting<br>• Dashboard data and notifications<br>• Proposal status logic | • Proposal submit, manage and status pages<br>• Both dashboards and notification dropdown<br>• Integrate with live APIs. Core complete by end of week. |
| **Week 4** (Oct 19 – Oct 23) | • Testing, bug fixes, deployment, API docs<br>• Only if the core is stable: extensions in the order set in section 2.2 (FR-24, then FR-20 / FR-21, FR-22, FR-23). Last 2 days: bug fixes only | • Testing, responsive and empty / error states, polish<br>• Extension screens in the same order<br>• README and final documentation |

---

## 7. Out of Scope (Phase 2)

Considered but excluded to keep the 23 Oct deadline realistic:

- OAuth for Instagram, TikTok and Facebook (manual entry is used instead)
- Any extension (FR-20 to FR-24) that is not finished before 23 Oct
- Push notifications, email digests and marketing emails. Email notifications and email verification if FR-24 is not finished. Password reset email stays in the core.
- Direct file uploads (images and videos)
- In-platform messaging and negotiation
- Payment processing
- Creators rating or reviewing brands
- Real-time features (websockets) and native mobile apps
- Account deletion (users cannot delete their whole account in this version)
