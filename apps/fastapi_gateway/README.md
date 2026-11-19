# LabFinder Real-Time Architecture & Gateway Guide

> **What does this system do?**  
> Whenever any data changes in the database (such as a lab updating its profile/executive summary, a customer posting a review, or a lab replying to a review), the change **instantly appears on everyone's screen in real time** without anyone having to refresh the page.

---

## 1. How All This Works (Simple Step-by-Step Logic)

Here is the exact lifecycle of an update from start to finish:

```
[1. User Action]
   Lab edits Profile / Customer submits Review
         │
         ▼
[2. Django Application]
   Standard Django View saves changes to Database (`branch.save()`, `review.save()`)
         │
         ▼
[3. PostgreSQL Database Trigger]
   A PL/pgSQL function (`notify_row_change`) fires automatically inside PostgreSQL.
   It converts the row to JSON and publishes it to the channel:
   PERFORM pg_notify('labfinder_realtime', payload);
         │
         ▼
[4. FastAPI Real-Time Gateway] (Port 8001)
   An async Python service running `LISTEN labfinder_realtime` picks up the event in milliseconds.
   It checks the `branch_id` and places the event into the subscriber channel: `lab:<branch_id>`.
         │
         ▼
[5. Browser Connection (SSE)]
   Every browser open to that lab has an active Server-Sent Events (SSE) connection:
   EventSource('http://localhost:8001/stream/lab/<branch_id>')
         │
         ▼
[6. Frontend JavaScript (`static/js/lab_realtime.js`)]
   The browser receives the event payload:
   { "table": "labs_branch", "action": "UPDATE", "data": { "description": "...", "lab_name": "..." } }
   It finds the elements on the page, updates their text, and pulses a soft green highlight!
```

### Why this architecture is better than alternatives:
* **No Database Polling**: The browser never asks the server "are there new updates?" every few seconds. It saves server CPU, bandwidth, and battery.
* **Instant Speed**: The notification takes less than **25 milliseconds** from database commit to browser display.
* **Database as Single Source of Truth**: Whether data is updated from Django Views, Django Admin, an API, or background tasks, the PostgreSQL trigger *always* fires. Nothing is ever missed.
* **Lightweight SSE**: Server-Sent Events (SSE) uses standard HTTP without the overhead, firewall blocks, or complex handshakes of WebSockets.

---

## 2. In How Many Places Is Real-Time Implemented?

Real-time is implemented across **6 database tables**, **4 UI templates**, and **several UI features**:

### A. Database Tables Watched by PostgreSQL Triggers
Configured in `apps/fastapi_gateway/config/watched_tables.json`:
1. **`labs_branch`**: Monitors changes to laboratory profiles (Executive summary, legal name, phone, email, facility address, city, pincode, min order value).
2. **`enquiries_labreview`**: Monitors new customer reviews (INSERT) and lab responses/replies (UPDATE).
3. **`labs_branchitem`**: Monitors test scope additions, edits, and active/inactive status toggles.
4. **`labs_accreditation`**: Monitors certificate and accreditation uploads/deletions.
5. **`labs_productservice`**: Monitors service offerings and testing capabilities.
6. **`enquiries_ordermessage`**: Monitors live order messages and chat communications between customer and lab.

---

### B. Templates & Screens Connected
1. **Customer Lab Detail Page** (`templates/labs/lab-detail.html`):
   * **Executive Summary / Overview**: Updates the Overview description paragraph in real time.
   * **Lab Name**: Updates hero title, breadcrumbs, and enquiry modal header.
   * **Address & Location**: Updates the address pill in real time.
   * **Customer Reviews**: Prepend new reviews to the top of the review list instantly without page refresh.
   * **Lab Responses**: When the lab replies to a review, the reply box appears under the customer's review card in real time.
   * **Review Counters**: Counter badges such as `(12 reviews)` increment automatically.

2. **Lab Portal Dashboard** (`templates/accounts/lab_portal.html`):
   * Initialized with `window.LabRealtime.init({ branchId: '{{ current_branch.id }}' })`.
   * Manages live event distribution across all tabs (Profile, Reviews, Scope, Dashboard).

3. **Lab Profile Tab** (`templates/accounts/includes/_lp_profile.html`):
   * **View Mode**: Updates Legal Lab Name, Phone Number, Contact Email, Facility Address, Pincode, and Executive Summary live.
   * **Edit Mode**: When "Save Changes" is clicked:
     * Saves via background AJAX fetch (`200 OK`).
     * Displays green success toast message.
     * Transitions smoothly back to View Mode (`/dashboard/?tab=profile`), removing `?edit=1` and showing the "Edit Profile" button.

4. **Lab Reviews Tab** (`templates/accounts/includes/_lp_reviews.html`):
   * When a customer submits a review:
     * The new review card is prepended to the top of `.lp-reviews-items` immediately.
     * An inline reply form is automatically bound so the lab manager can reply with zero reload.
     * Review counter increments automatically.
     * A toast appears: *"New customer review received from [Customer Name]"*.

5. **Review Details Page** (`templates/accounts/review-details.html`):
   * Initialized with `window.LabRealtime.init({ branchId: '{{ b_id }}' })` for live review interactions.

---

## 3. How to Start and Run the Service

### Step 1: Ensure PostgreSQL Triggers Are Installed
The triggers are installed via Django management command:
```bash
./venv/bin/python manage.py install_realtime_triggers
```
*(Only needs to be run once, or if you modify table definitions).*

### Step 2: Start the FastAPI Real-Time Gateway
In your terminal:
```bash
PYTHONPATH=apps/fastapi_gateway ./venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```
You should see:
```text
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001
[INFO] labfinder-realtime: Postgres connection established for LISTEN on 'labfinder_realtime'
```

### Step 3: Health Check
Verify the service is active:
```bash
curl http://localhost:8001/health
```
Output:
```json
{"status": "ok", "active_channels": 1, "total_listeners": 1}
```

---

## 4. Frontend CSS Classes Reference

Any HTML element in any template can automatically receive live updates by adding any of these CSS classes:

| Class Name | What It Updates in Real Time | Example Element |
| :--- | :--- | :--- |
| `.js-realtime-executive-summary` / `.lp-overview-desc` | Executive Summary / About Us text | `<p class="js-realtime-executive-summary">` |
| `.js-realtime-lab-name` | Legal Lab Name | `<h1 class="js-realtime-lab-name">` |
| `.js-realtime-contact-mobile` | Contact Phone Number | `<div class="js-realtime-contact-mobile">` |
| `.js-realtime-contact-email` | Contact Email | `<div class="js-realtime-contact-email">` |
| `.js-realtime-address` / `.js-realtime-lab-address` | Full address (Address, City, Pincode) | `<span class="js-realtime-address">` |
| `.js-realtime-city` | City name | `<span class="js-realtime-city">` |
| `.js-realtime-lab-pincode` | Postal Code | `<span class="js-realtime-lab-pincode">` |
| `.js-realtime-min-order` | Minimum Order Value | `<span class="js-realtime-min-order">` |

When any of these elements are updated live, `LabRealtime.highlightElement(el)` flashes a subtle soft pulse so the user visually notices the change.
