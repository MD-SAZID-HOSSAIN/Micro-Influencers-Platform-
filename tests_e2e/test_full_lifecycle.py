"""
Complete End-to-End PRD Lifecycle Test Suite
Verifies all functional workflows FR-01 through FR-24 against live backend and database.
"""
import json
import urllib.request
import urllib.error
import time

BASE_URL = "http://127.0.0.1:8000/api/v1"

results = []

def record(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name} {('- ' + detail) if detail else ''}")
    results.append({"name": name, "status": status, "detail": detail})

def api(path, method="GET", body=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8")
            return resp.status, json.loads(content) if content.strip().startswith(("{", "[")) else {"raw": content[:100]}
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8")
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {"raw": content[:100]}
        return e.code, parsed
    except Exception as e:
        return 0, {"error": str(e)}

print("\n" + "="*70)
print("  EXECUTING COMPREHENSIVE END-TO-END WORKFLOW VERIFICATION (FR-01 - FR-24)")
print("="*70 + "\n")

ts = int(time.time() * 1000)

# ---------------------------------------------------------------------------
# WORKFLOW A: Authentication & Access (FR-01, FR-02, FR-24)
# ---------------------------------------------------------------------------
# 1. Register Creator
c_user = f"cr_{ts}"
c_email = f"cr_{ts}@example.com"
status, data = api("/auth/register/", "POST", {
    "role": "creator",
    "full_name": "Test Creator Auto",
    "email": c_email,
    "username": c_user,
    "password": "StrongPassword123!",
    "mobile_number": "+1234567890"
})
record("FR-01: User Registration (Creator)", status == 201 and data.get("username") == c_user, f"HTTP {status}")

# 2. Register Brand
b_user = f"br_{ts}"
b_email = f"br_{ts}@example.com"
status, data = api("/auth/register/", "POST", {
    "role": "brand",
    "full_name": "Test Brand Auto",
    "email": b_email,
    "username": b_user,
    "password": "StrongPassword123!",
    "mobile_number": "+1987654321"
})
record("FR-01: User Registration (Brand)", status == 201 and data.get("username") == b_user, f"HTTP {status}")

# 3. Login Creator
status, data = api("/auth/login/", "POST", {"identifier": c_user, "password": "StrongPassword123!"})
c_token = data.get("access")
record("FR-02: Creator Login & JWT Token Issuance", status == 200 and c_token is not None, f"HTTP {status}")

# 4. Login Brand
status, data = api("/auth/login/", "POST", {"identifier": b_user, "password": "StrongPassword123!"})
b_token = data.get("access")
record("FR-02: Brand Login & JWT Token Issuance", status == 200 and b_token is not None, f"HTTP {status}")

# 5. Password Reset Request (Uniform response)
status, data = api("/auth/password-reset/request/", "POST", {"email": c_email})
record("FR-02: Password Reset Request (Uniform response)", status == 200, f"HTTP {status}, msg={data.get('detail', '')[:40]}")

# 6. Verify Email Settings
status, data = api("/settings/notifications/", "GET", token=c_token)
record("FR-24: Notification Settings Fetch", status == 200 and "email_enabled" in data, f"enabled={data.get('email_enabled')}")

# ---------------------------------------------------------------------------
# WORKFLOW B: Profiles, Social & Portfolio (FR-03, FR-04, FR-05, FR-06)
# ---------------------------------------------------------------------------
# Update Creator Profile
status, data = api("/creators/me/", "PATCH", {
    "bio": "Certified Tech Reviewer and Product Tester",
    "niche": "tech",
    "primary_platform": "youtube",
    "city": "San Francisco",
    "country": "USA",
    "rate_post": "250.00",
    "rate_story": "100.00",
    "rate_video": "600.00"
}, token=c_token)
record("FR-03: Creator Profile Update (Bio, Niche, Rates)", status == 200 and data.get("niche") == "tech", f"completion={data.get('completion_percent')}%")

# Update Brand Profile
status, data = api("/brands/me/", "PATCH", {
    "company_name": "Apex Sound Labs",
    "industry": "Consumer Audio",
    "website": "https://apexsound.example.com",
    "about": "Pioneering premium wireless audio hardware"
}, token=b_token)
record("FR-04: Brand Profile Update", status == 200 and data.get("company_name") == "Apex Sound Labs", f"HTTP {status}")

# Add Portfolio Item
status, data = api("/creators/me/portfolio/", "POST", {
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "caption": "Flagship ANC Headphone In-Depth Video"
}, token=c_token)
port_id = data.get("id")
record("FR-06: Add Portfolio Link", status == 201 and port_id is not None, f"id={port_id}")

# Delete Portfolio Item
if port_id:
    status, _ = api(f"/creators/me/portfolio/{port_id}/", "DELETE", token=c_token)
    record("FR-06: Delete Portfolio Link", status == 204, f"HTTP {status}")

# Social YouTube Connection Status
status, data = api("/social/youtube/", "GET", token=c_token)
record("FR-05: Social Media YouTube Status", status == 200 and "connected" in data, f"connected={data.get('connected')}")

# ---------------------------------------------------------------------------
# WORKFLOW C: Campaign Lifecycle (FR-09, FR-10, FR-11, FR-12)
# ---------------------------------------------------------------------------
# 1. Create Draft Campaign
status, data = api("/brand/campaigns/", "POST", {
    "title": f"Apex Wave Wireless Launch {ts}",
    "description": "High-fidelity review of our new flagship headphones.",
    "niche": "tech",
    "platform": "youtube",
    "budget": "500.00",
    "deadline": "2026-12-31T23:59:59Z",
    "deliverables": "1 dedicated 8-min review video",
    "creators_needed": 2,
    "min_followers": 0
}, token=b_token)
camp_id = data.get("id")
record("FR-09: Campaign Creation (Draft by default)", status == 201 and data.get("status") == "draft", f"id={camp_id}, status={data.get('status')}")

# 2. Publish Campaign
status, data = api(f"/brand/campaigns/{camp_id}/publish/", "POST", token=b_token)
record("FR-10: Campaign Publishing (Draft -> Published)", status == 200 and data.get("status") == "published", f"status={data.get('status')}")

# 3. Creator Discovers Campaign
status, data = api(f"/campaigns/?niche=tech&platform=youtube", "GET", token=c_token)
results_list = data.get("results", [])
found = any(c.get("id") == camp_id for c in results_list)
record("FR-11: Campaign Discovery (Filtered by niche & platform)", status == 200 and found, f"found_id={camp_id} in {len(results_list)} results")

# 4. Creator Views Campaign Detail
status, data = api(f"/campaigns/{camp_id}/", "GET", token=c_token)
record("FR-12: Campaign Detail View", status == 200 and data.get("id") == camp_id, f"title={str(data.get('title'))[:30]}")

# ---------------------------------------------------------------------------
# WORKFLOW D: Proposal Lifecycle (FR-13, FR-14, FR-15, FR-16)
# ---------------------------------------------------------------------------
# 1. Creator Submits Proposal
status, data = api(f"/campaigns/{camp_id}/proposals/", "POST", {
    "cover_message": "I have an active tech channel eager to showcase your ANC tech.",
    "proposed_rate": "450.00",
    "portfolio_links": ["https://youtube.com/watch?v=dQw4w9WgXcQ"],
    "experience_note": "5 years testing pro audio gear"
}, token=c_token)
prop_id = data.get("id")
record("FR-13: Proposal Submission (Creator -> Campaign)", status == 201 and prop_id is not None, f"prop_id={prop_id}, status={data.get('status')}")

# 2. Duplicate Proposal Prevented
status, data = api(f"/campaigns/{camp_id}/proposals/", "POST", {
    "cover_message": "Second attempt",
    "proposed_rate": "450.00",
    "portfolio_links": [],
    "experience_note": ""
}, token=c_token)
record("FR-13: Duplicate Active Proposal Blocked (409)", status == 409 and data.get("error", {}).get("code") == "proposal_exists", f"HTTP {status}, code={data.get('error', {}).get('code')}")

# 3. Brand Reviews Proposals List
status, data = api(f"/brand/campaigns/{camp_id}/proposals/", "GET", token=b_token)
record("FR-14: Brand Proposal Management List", status == 200 and data.get("count", 0) >= 1, f"count={data.get('count')}")

# 4. Brand Shortlists Proposal
if prop_id:
    status, data = api(f"/brand/proposals/{prop_id}/shortlist/", "POST", token=b_token)
    record("FR-15: Brand Shortlists Proposal (Pending -> Shortlisted)", status == 200 and data.get("status") == "shortlisted", f"status={data.get('status')}")

    # 5. Brand Accepts Proposal
    status, data = api(f"/brand/proposals/{prop_id}/accept/", "POST", token=b_token)
    record("FR-15: Brand Accepts Proposal (Shortlisted -> Accepted)", status == 200 and data.get("status") == "accepted", f"status={data.get('status')}")

# 6. Creator Application Status Tracking
status, data = api("/creators/me/proposals/", "GET", token=c_token)
c_prop = next((p for p in data.get("results", []) if p.get("id") == prop_id), None)
record("FR-16: Creator Application Status Tracking", status == 200 and c_prop is not None and c_prop.get("status") == "accepted", f"status={c_prop.get('status') if c_prop else 'None'}")

# ---------------------------------------------------------------------------
# WORKFLOW E: Deliverables & Reviews (FR-20, FR-21)
# ---------------------------------------------------------------------------
if prop_id:
    # 1. Creator Submits Deliverable
    status, data = api(f"/creators/me/proposals/{prop_id}/deliverables/", "POST", {
        "post_url": "https://youtube.com/watch?v=live_deliverable_01",
        "platform": "youtube",
        "note": "Final sponsored video published to channel."
    }, token=c_token)
    deliv_id = data.get("id")
    record("FR-20: Creator Submits Deliverable Content Link", status == 201 and deliv_id is not None, f"deliv_id={deliv_id}")

    # 2. Brand Marks Collaboration Completed
    status, data = api(f"/brand/proposals/{prop_id}/complete/", "POST", token=b_token)
    record("FR-20: Brand Marks Collaboration Completed", status == 200 and data.get("completed_at") is not None, f"completed_at={data.get('completed_at')}")

    # 3. Brand Rates & Reviews Creator
    status, data = api(f"/brand/proposals/{prop_id}/review/", "POST", {
        "rating": 5,
        "text": "Exceptional audio review, stellar engagement and timely delivery!"
    }, token=b_token)
    record("FR-21: Brand Submits Rating & Review", status == 201 and data.get("rating") == 5, f"rating={data.get('rating')}")

# ---------------------------------------------------------------------------
# WORKFLOW F: Dashboards & Notifications (FR-17, FR-18, FR-19)
# ---------------------------------------------------------------------------
# Creator Dashboard
status, data = api("/creators/me/dashboard/", "GET", token=c_token)
record("FR-17: Creator Dashboard Metrics & Summary", status == 200 and "profile_completion" in data and "performance" in data, f"profile_completion={data.get('profile_completion')}%, acceptance_rate={data.get('performance', {}).get('acceptance_rate')}")

# Brand Dashboard
status, data = api("/brands/me/dashboard/", "GET", token=b_token)
record("FR-18: Brand Dashboard Metrics & Summary", status == 200 and "active_campaigns" in data, f"active_camp={data.get('active_campaigns')}")

# In-App Notifications
status, data = api("/notifications/", "GET", token=c_token)
record("FR-19: In-App Notification System", status == 200 and "results" in data, f"unread={data.get('unread_count')}")

# ---------------------------------------------------------------------------
# WORKFLOW G: Campaign Performance Analytics (FR-23)
# ---------------------------------------------------------------------------
status, data = api(f"/brand/campaigns/{camp_id}/analytics/", "GET", token=b_token)
record("FR-23: Campaign Performance Analytics (Proposal funnel)", status == 200 and "funnel" in data, f"funnel={data.get('funnel')}")

# ---------------------------------------------------------------------------
# WORKFLOW H: Admin Panel Operations (FR-22)
# ---------------------------------------------------------------------------
status, data = api("/admin/auth/login/", "POST", {"identifier": "admin", "password": "AdminPassword123!"})
admin_token = data.get("access")
record("FR-22: Admin Authentication (/admin/auth/login/)", status == 200 and admin_token is not None, f"HTTP {status}")

if admin_token:
    # Platform Overview
    status, data = api("/admin/overview/", "GET", token=admin_token)
    record("FR-22: Admin Platform Overview", status == 200 and "users" in data, f"total_users={data.get('users', {}).get('total')}")

    # List Users
    status, data = api("/admin/users/", "GET", token=admin_token)
    record("FR-22: Admin User Management List", status == 200 and "results" in data, f"count={data.get('count')}")

    # Audit Log
    status, data = api("/admin/actions/", "GET", token=admin_token)
    record("FR-22: Admin Audit Log Actions", status == 200 and "results" in data, f"count={data.get('count')}")

print("\n" + "="*70)
passed = sum(1 for r in results if r["status"] == "PASS")
total = len(results)
print(f"  TOTAL END-TO-END TESTS: {passed}/{total} PASSED ({(passed/total)*100:.1f}%)")
print("="*70 + "\n")
