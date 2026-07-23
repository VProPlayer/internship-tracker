# Internship Tracker

Monitors 45 company careers pages every weekday evening and emails you a digest of new internship postings. No web server, no dashboard — just a Python script and a GitHub Actions cron job.

---

## Subscribe

Get the digest in your inbox every weekday evening. Two ways to request access, both free:

- **[Ask to join via Google Groups](https://groups.google.com/g/internship-tracker)** — click *Ask to join group*. Requires a Google account.
- **Ask to join by email** — send a blank email to **internship-tracker+subscribe@googlegroups.com** and reply to the confirmation. No Google account needed.

Requests are reviewed by the group owner, so there may be a short wait before the first digest arrives.

To leave at any time, email **internship-tracker+unsubscribe@googlegroups.com** or use the group page. The list is one-way: only the tracker posts, so you'll never receive mail from other subscribers.

Want a company added to the list? [**Request one here.**](https://forms.gle/coZd4rP7JtiTjFFW6)

---

## What It Does

1. Fetches job postings from companies of your choice using their native APIs (Greenhouse, Workday, Ashby, Lever, SmartRecruiters, Eightfold, Phenom, iCIMS, Amazon) or, for companies without a structured API, scrapes the careers page via Jina Reader and extracts postings with Gemini Flash.
2. Compares every posting against a Supabase table (`seen_jobs`) to deduplicate across runs.
3. If new postings are found, sends one HTML email digest (with a plain-text fallback) to a Google Group, which fans it out to every subscriber.
4. Runs automatically Monday–Friday at 23:00 UTC (6:00 PM EST) via GitHub Actions. If the run fails entirely, a separate failure alert is sent.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Scheduler | GitHub Actions cron (`0 23 * * 1-5`) |
| Structured APIs | Greenhouse, Workday CXS, Ashby, Lever, SmartRecruiters, Eightfold, Phenom, iCIMS, Amazon |
| Unstructured sites | Jina Reader (page → plain text) + Gemini Flash (text → structured JSON) |
| Deduplication | Supabase (Postgres) |
| Email | Python `smtplib` (stdlib) over SMTP-SSL, Material-Expressive dark HTML template, 3x retry |
| Distribution | Google Group fan-out — one message per run, Google handles delivery |
| Runtime | Python 3.12, no web framework |

The Gemini model in use is `gemini-3.5-flash-lite`, set by the `GEMINI_MODEL` constant in `fetchers/jina.py`. All fetchers share HTTP helpers in `fetchers/__init__.py` with automatic retry/backoff and offset pagination, plus the `is_relevant` / `is_us_country` / `is_us_location` filters.

Email dispatch retries 3 times with 5s/10s backoff on transient SMTP failures. Authentication errors and recipient rejections are raised immediately rather than retried — neither self-heals, and repeating a failed login risks a Google account lockout.

Jina supports a second key: if the primary returns HTTP 402 (token balance exhausted), the run fails over to `JINA_API_KEY_FALLBACK` for the remainder of the run. Remaining balances for both keys are printed in the email footer.

---

## Onboarding

### 1. Fork the Repository

Fork this repo to your own GitHub account. All subsequent steps apply to your fork.

### 2. Create the Supabase Table

Go to your [Supabase project](https://supabase.com), open the SQL Editor, and run:

```sql
create table seen_jobs (
  id          text primary key,
  company     text not null,
  title       text not null,
  url         text not null,
  location    text,
  first_seen  timestamptz not null,
  last_seen   timestamptz not null,
  notified    boolean not null default false
);
```

The table name must be `seen_jobs` exactly — it is hardcoded in `diff.py`.

### 3. Gather Your API Keys

You need the following before proceeding:

| Key | Where to get it |
|---|---|
| `SUPABASE_URL` | Supabase dashboard → Project Settings → API → Project URL |
| `SUPABASE_KEY` | Supabase dashboard → Project Settings → API → `anon` public key |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/app/apikey) |
| `SMTP_USER` | The Gmail address the digest is sent from |
| `SMTP_PASSWORD` | A Google [App Password](https://myaccount.google.com/apppasswords) for that account (requires 2-Step Verification; this is **not** your account password) |
| `JINA_API_KEY` | [Jina AI](https://jina.ai/) → API Keys (optional, but recommended — unauthenticated requests are rate-limited) |
| `JINA_API_KEY_FALLBACK` | A second Jina key from a separate account (optional — used automatically when the primary key runs out of tokens) |

### 4. Add Secrets to GitHub Actions

GitHub Actions reads secrets from your repository settings — **not** from your local `.env` file. You must add them manually through the GitHub UI.

In your forked repository, go to **Settings → Secrets and variables → Actions → New repository secret** and add each of the keys below by their exact names:

| Secret name | Value |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL (e.g. `https://xxxx.supabase.co`) |
| `SUPABASE_KEY` | Your Supabase anon key (starts with `sb_publishable_` on new accounts) |
| `GEMINI_API_KEY` | Your Google AI Studio key |
| `SMTP_USER` | The sending Gmail address |
| `SMTP_PASSWORD` | The Google App Password for that address |
| `OWNER_EMAIL` | Your own address — failure alerts go here, never to the group |
| `JINA_API_KEY` | Your Jina AI key (optional) |
| `JINA_API_KEY_FALLBACK` | A backup Jina key used when the primary is exhausted (optional) |
| `RECIPIENT_EMAIL` | Your Google Group address, e.g. `internship-digest@googlegroups.com` |

The workflow at `.github/workflows/run.yml` injects these as environment variables at runtime. Your local `.env` file is ignored by GitHub Actions entirely — it only exists for local runs.

### 5. Create the Google Group

Subscribers are managed by a Google Group rather than by this codebase. The tracker sends exactly **one** email per run — to the group — and Google fans it out to every member, handling delivery, bounces, unsubscribes, and a public archive. There is no subscriber table and no per-recipient loop to maintain.

1. Go to [groups.google.com](https://groups.google.com) → **Create group**.
2. Give it a name and address (e.g. `internship-digest@googlegroups.com`).
3. Under **Posting policies → Who can post**, choose *Group managers*. Then add your `SMTP_USER` address under **People → Add members** and promote it to **Manager** (not Owner — it holds a standing app password, and Manager is the least privilege that can post under this policy). This makes the group one-way: the tracker broadcasts, and subscribers cannot mail each other.
4. Set **Who can join** to *Anyone can ask* if you want open signup, or *Only invited users* if you'd rather approve each person.
5. Under **Settings → Member privacy**, hide the member list so subscribers can't harvest each other's addresses.
6. Put the group address in the `RECIPIENT_EMAIL` secret.

Members subscribe and unsubscribe themselves through the Google Groups page — share that link and you are done. If you prefer a friendlier front door, point a Google Form at prospective subscribers and add them from the responses.

> **Why not send to each subscriber directly?** Sending mail to third parties requires a domain you own and have verified with an email provider. Delegating fan-out to a Google Group avoids that requirement entirely, and hands you unsubscribe handling and CAN-SPAM-appropriate list management for free.

### 6. Trigger a Manual Run

To verify everything is wired up before waiting for the cron:

1. Go to your repository on GitHub.
2. Click the **Actions** tab.
3. Select **Internship Tracker** from the left sidebar.
4. Click **Run workflow** → **Run workflow**.

> **Note:** GitHub only registers a workflow in the Actions UI after it detects the workflow file on the default branch. If **Internship Tracker** does not appear in the sidebar, make any small commit and push — GitHub will index the workflow on the next push and it will appear within a minute.

Check the run logs for `[OK]` lines per company and a final count of new jobs found. If new jobs exist, you should receive an email within a minute of the run completing.

---

## Adding a New Company

All companies are defined in `companies.json`. Each entry needs a `name`, a `type`, and type-specific fields.

### Greenhouse

Find the company's Greenhouse slug — it appears in their job board URL, e.g. `https://boards.greenhouse.io/stripe` → slug is `stripe`.

```json
{
  "name": "STRIPE",
  "type": "greenhouse",
  "slug": "stripe"
}
```

### Workday

The tenant and site name appear in the Workday careers URL. For example, `https://wd5.myworkdayjobs.com/Nike_External_Career_Site` → tenant is `Nike`, site is `Nike_External_Career_Site`.

```json
{
  "name": "NIKE",
  "type": "workday",
  "tenant": "Nike",
  "site": "Nike_External_Career_Site"
}
```

### Ashby

The board name is the last path segment of the Ashby job board URL, e.g. `https://jobs.ashbyhq.com/openai` → `openai`.

```json
{
  "name": "OPENAI",
  "type": "ashby",
  "board_handle": "openai"
}
```

### Lever

The slug appears in the Lever board URL, e.g. `https://jobs.lever.co/zoox` → `zoox`.

```json
{
  "name": "ZOOX",
  "type": "lever",
  "handle": "zoox"
}
```

### SmartRecruiters

The company identifier appears in the careers URL, e.g. `https://careers.smartrecruiters.com/AstroscaleUS` → `AstroscaleUS`.

```json
{
  "name": "ASTROSCALE",
  "type": "smartrecruiters",
  "company_id": "AstroscaleUS"
}
```

### Eightfold

Tenants are hosted at `<company>.eightfold.ai`; the `domain` is the tenant's corporate domain.

```json
{
  "name": "NETAPP",
  "type": "eightfold",
  "host": "netapp.eightfold.ai",
  "domain": "netapp.com"
}
```

### Phenom

For Phenom People–powered boards. `api_base` is the careers host, `domain` the tenant domain. Optional `title_exclude` drops postings whose title contains any of the listed phrases (used to filter Microsoft's PhD-only research internships).

```json
{
  "name": "MICROSOFT",
  "type": "phenom",
  "api_base": "https://apply.careers.microsoft.com",
  "domain": "microsoft.com",
  "title_exclude": ["Research Intern"]
}
```

### iCIMS

Use the base URL of the company's iCIMS-powered careers page.

```json
{
  "name": "LOCKHEED MARTIN",
  "type": "icims",
  "url": "https://www.lockheedmartinjobs.com/search-jobs"
}
```

### Custom (Jina + Gemini)

For any company that does not use one of the above platforms, use `"type": "custom"` with the URL of their careers listing page. Jina Reader will fetch the page as plain text and Gemini will extract the postings.

```json
{
  "name": "PALANTIR",
  "type": "custom",
  "url": "https://www.palantir.com/careers/students/"
}
```

Custom type results depend on how well the careers page renders through Jina. Pages that load entirely via JavaScript client-side rendering may return sparse results.

---

## Running Locally

### Prerequisites

- Python 3.12+
- A `.env` file in the project root (see below)

### Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/internship-tracker.git
cd internship-tracker

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-anon-key
GEMINI_API_KEY=your-gemini-key
JINA_API_KEY=your-jina-key
SMTP_USER=your-sender@gmail.com
SMTP_PASSWORD=your-16-char-app-password
RECIPIENT_EMAIL=your-group@googlegroups.com
OWNER_EMAIL=you@example.com
```

`python-dotenv` loads this file automatically when `main.py` runs. Do not commit `.env` — it is listed in `.gitignore`.

### Run

```bash
python main.py
```

Output is printed per company as each fetcher completes. A summary line at the end shows how many new jobs were found. If any new jobs exist, an email is sent immediately.

Errors from individual companies are logged but do not abort the run. The script only exits with a non-zero code if every single company fails.

---

## Project Structure

```
internship-tracker/
├── main.py               # Entry point — orchestrates fetch, diff, notify
├── diff.py               # Supabase deduplication logic
├── notify.py             # Email formatting and SMTP dispatch
├── companies.json        # List of tracked companies
├── requirements.txt
├── fetchers/
│   ├── __init__.py       # Shared helpers: http_get/http_post (retry), offset_paginate,
│   │                     #   KEYWORD_RE, is_relevant, is_us_country, is_us_location, make_id
│   ├── greenhouse.py     # Greenhouse JSON API
│   ├── workday.py        # Workday CXS API
│   ├── ashby.py          # Ashby job board API
│   ├── lever.py          # Lever postings API
│   ├── smartrecruiters.py# SmartRecruiters postings API
│   ├── eightfold.py      # Eightfold JSON API (NetApp)
│   ├── phenom.py         # Phenom People search API
│   ├── amazon.py         # Amazon jobs search API
│   ├── amd.py            # AMD Jibe search API (registered, currently unused)
│   ├── icims.py          # iCIMS REST API
│   └── jina.py           # Jina Reader + Gemini Flash fallback (with key failover)
└── .github/
    └── workflows/
        └── run.yml       # GitHub Actions cron definition
```
