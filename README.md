# Internship Tracker

Monitors 57 company careers pages every weekday evening and emails you a digest of new internship postings. No web server, no dashboard — just a Python script and a GitHub Actions cron job.

📋 **[See all 57 tracked companies →](#tracked-companies)** (at the bottom of this page)

---

## How This Is Different

Most internship trackers are either a job board you have to remember to visit, or a
scraped aggregator that indexes postings after some third party has already picked them up.
This one is built the other way around:

- **It comes to you.** One email digest per run, straight to your inbox. Nothing to check,
  no site to open, no feed to scroll.
- **It runs every weekday, automatically.** A GitHub Actions cron fires Monday–Friday
  evening. New postings reach you within one business day of appearing — not in real time,
  but without you doing anything.
- **It reads the companies' own job APIs.** Postings come from each employer's actual ATS
  (Greenhouse, Workday, Ashby, Oracle, and so on), so a listing shows up as soon as the
  company publishes it, rather than waiting for an aggregator to crawl and re-index it.
- **The company list is yours.** 57 hand-picked employers, not an algorithm's idea of what
  you want. Adding one is a few lines of JSON — see [Adding a New Company](#adding-a-new-company).
- **It filters for undergrads specifically.** PhD, MS, MBA, and graduate-only internships
  are excluded, along with senior/staff/director titles and non-technical roles. PM-track
  internships ("Product Manager: Internship Opportunities") are kept — only the staff roles
  that *run* an intern program ("Internship Program Manager") are dropped. A search for
  "intern" on most boards buries you in postings you cannot apply to.
- **You are told once.** A local ledger tracks every posting it has seen, so a role that
  stays open for two months is emailed to you exactly once, never re-sent.
- **It tells you when it might have missed something.** Page caps, oversized careers pages,
  and malformed postings all raise a warning by email instead of vanishing into a log.
- **No account, no tracking, no middleman.** Fork it and it is entirely yours — your own
  API keys, your own list, your own inbox. Nothing about you is collected or sold.

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

1. Fetches job postings from companies of your choice using their native APIs (Greenhouse, Workday, Ashby, Lever, SmartRecruiters, Eightfold, Phenom, Oracle Recruiting Cloud, Amazon) or, for companies without a structured API, scrapes the careers page via Jina Reader and extracts postings with Gemini Flash.
2. Compares every posting against a local JSON ledger (`seen_jobs.json`, committed in the repo) to deduplicate across runs. Postings unseen for 60 days are pruned so the ledger stays bounded.
3. If new postings are found, sends one HTML email digest (with a plain-text fallback) to a Google Group, which fans it out to every subscriber.
4. Runs automatically Monday–Friday at 23:00 UTC (6:00 PM EST) via GitHub Actions. If the run fails entirely, a separate failure alert is sent.

The failure alert also carries **partial-loss warnings**, not just hard errors. A fetcher that hits its page cap, a careers page longer than the scan budget, or a posting discarded for a missing title or URL are all recorded and surfaced by email — these were previously only visible as `[WARN]` lines buried in the Actions log.

> **On timing:** the cron is set for 6:00 PM EST, but GitHub Actions does not run scheduled jobs on the dot — during busy periods it queues them, so in practice the digest tends to land around **8:00 PM EST**. This is expected behaviour, not a fault. For a guaranteed time, trigger the workflow manually (see step 6 in Onboarding).

---

## Tech Stack

| Layer | Tool |
|---|---|
| Scheduler | GitHub Actions cron (`0 23 * * 1-5`) |
| Structured APIs | Greenhouse, Workday CXS, Ashby, Lever, SmartRecruiters, Eightfold, Phenom, Oracle Recruiting Cloud, Amazon |
| Unstructured sites | Jina Reader (page → plain text) + Gemini Flash (text → structured JSON) |
| Deduplication | Local JSON ledger (`seen_jobs.json`), committed back by CI each run |
| Email | Python `smtplib` (stdlib) over SMTP-SSL, Material 3 Expressive HTML template (light/dark adaptive), 3x retry |
| Distribution | Google Group fan-out — one message per run, Google handles delivery |
| Runtime | Python 3.12, no web framework |

The Gemini model in use is `gemini-3.5-flash-lite`, set by the `GEMINI_MODEL` constant in `fetchers/jina.py`. All fetchers share HTTP helpers in `fetchers/__init__.py` with automatic retry/backoff and offset pagination, plus the `is_relevant` / `is_us_country` / `is_us_location` filters and the `labeled_errors` context manager that tags a failure with the company that caused it.

Country matching goes through `is_us_country` rather than per-fetcher string comparisons. Fetchers used to carry their own spelling lists, which drifted — a platform returning `United States` instead of `US` had every posting silently dropped.

Email dispatch retries 3 times with 5s/10s backoff on transient SMTP failures. Authentication errors and recipient rejections are raised immediately rather than retried — neither self-heals, and repeating a failed login risks a Google account lockout.

Long careers pages are **chunked rather than truncated**. A page over `CONTENT_LIMIT` (40,000 chars) is split into up to `MAX_CHUNKS` (4) overlapping slices, each sent to Gemini separately and the results merged and de-duplicated; the `OVERLAP` (2,000 chars) keeps a posting that straddles a boundary intact in at least one slice. Previously everything past the limit was discarded — Apple was losing roughly 20% of its page.

To keep that from multiplying cost, a chunk is **skipped before any Gemini call** if it contains no `intern` / `co-op` / `student` keyword anywhere. The extraction prompt requires the keyword in the job title, so a slice of nav, cookie banner, footer, or embedded theme JSON provably has nothing to find. This is a local regex (`KEYWORD_RE`), not a Jina or Gemini feature, so it costs nothing — it reduces Gemini calls but not Jina reads, since a page must be fetched before it can be inspected.

Jina fetching climbs three auth tiers, cheapest first, escalating only when the current one stops working: the keyless **free tier** is used until it rate-limits or repeatedly fails, then **key 1** (`JINA_API_KEY`) until its token balance is exhausted (HTTP 402), then **key 2** (`JINA_API_KEY_FALLBACK`) until it too is exhausted, after which the run hard-fails. A tier whose key is unset is skipped, so with no `JINA_API_KEY` the free tier falls straight through to `JINA_API_KEY_FALLBACK`. Escalation is one-way and lasts the rest of the run. The email footer reports remaining balances only for the keys that run actually used — a free-tier-only run shows no balance line.

---

## Onboarding

### 1. Fork the Repository

Fork this repo to your own GitHub account. All subsequent steps apply to your fork.

### 2. The Deduplication Ledger

There is no database to provision. Seen postings are tracked in `seen_jobs.json`
at the repo root, and the GitHub Action commits the updated file back after each
run (see `.github/workflows/run.yml`). On a fresh fork, either keep the existing
ledger or reset it to an empty list:

```json
[]
```

Each entry has the shape `{ id, company, title, url, location, first_seen,
last_seen, notified }` — the schema is defined by `diff.py`, which reads and
writes this file. A posting notifies only the first time its `id` is seen; every
subsequent run refreshes its `last_seen`. Rows unseen for `RETENTION_DAYS` (60,
in `diff.py`) are pruned, so only genuinely-closed roles age out and the ledger
stays bounded.

### 3. Gather Your API Keys

You need the following before proceeding:

| Key | Where to get it |
|---|---|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/app/apikey) |
| `SMTP_USER` | The Gmail address the digest is sent from |
| `SMTP_PASSWORD` | A Google [App Password](https://myaccount.google.com/apppasswords) for that account (requires 2-Step Verification; this is **not** your account password) |
| `JINA_API_KEY` | [Jina AI](https://jina.ai/) → API Keys (key 1 — optional, but recommended; the keyless free tier is rate-limited) |
| `JINA_API_KEY_FALLBACK` | A second Jina key from a separate account (key 2 — optional; used automatically once key 1 runs out of tokens) |

### 4. Add Secrets to GitHub Actions

GitHub Actions reads secrets from your repository settings — **not** from your local `.env` file. You must add them manually through the GitHub UI.

In your forked repository, go to **Settings → Secrets and variables → Actions → New repository secret** and add each of the keys below by their exact names:

| Secret name | Value |
|---|---|
| `GEMINI_API_KEY` | Your Google AI Studio key |
| `SMTP_USER` | The sending Gmail address |
| `SMTP_PASSWORD` | The Google App Password for that address |
| `OWNER_EMAIL` | Your own address — failure alerts go here, never to the group |
| `JINA_API_KEY` | Your Jina AI key — key 1 (optional) |
| `JINA_API_KEY_FALLBACK` | A backup Jina key — key 2, used when key 1 is exhausted (optional) |
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

### Oracle Recruiting Cloud

For Oracle Fusion–backed careers sites. Each tenant sits on its own Fusion pod host. Two
different site identifiers are needed and they are **not** interchangeable: `site_number` is
the API's `siteNumber` argument, while `site_slug` is the segment used in public job URLs
(using `site_number` in a URL redirects). Find the host and slug by opening a job posting
from the company's careers page and reading the address bar.

```json
{
  "name": "HONEYWELL",
  "type": "orc",
  "host": "ibqbjb.fa.ocs.oraclecloud.com",
  "site_number": "CX_1001",
  "site_slug": "Honeywell"
}
```

Some tenants ignore `site_number` entirely and return the full requisition set regardless
of the value passed. Their keyword search is also fuzzy — a search for `intern` matches
"Internal Auditor" — so the shared title filters do the real work.

### iCIMS — non-functional

> **`type: "icims"` does not work and should not be used.** iCIMS serves HTML rather than
> JSON and exposes no unauthenticated search API, so `fetchers/icims.py` fails on every
> board tested. It remains in the dispatch table only so existing configs error loudly
> rather than silently. **Use `type: "custom"` for iCIMS companies** — that is how Rivian,
> SAS, and Joby Aviation are configured.

### Custom (Jina + Gemini)

For any company that does not use one of the above platforms, use `"type": "custom"` with the URL of their careers listing page. Jina Reader will fetch the page as plain text and Gemini will extract the postings.

```json
{
  "name": "PALANTIR",
  "type": "custom",
  "url": "https://www.palantir.com/careers/students/"
}
```

Custom type results depend on how well the careers page renders through Jina. Pages that load their job rows entirely via client-side JavaScript return **nothing** — Jina delivers the page chrome, and the run spends a Jina read plus at least one Gemini call to extract zero postings. Ericsson, Toshiba Global Commerce, and Extreme Networks were all rejected on exactly this basis.

Before adding a `custom` entry, confirm the page is worth fetching:

```bash
curl -s "https://r.jina.ai/<CAREERS_URL>" | grep -ci "intern"
```

A handful of hits usually means nav links and cookie text only. Real listings show up as
repeated job titles with distinct URLs — inspect the output rather than trusting the count.
If there are none, find the XHR endpoint the page calls in your browser's network tab and
write a small fetcher against it instead; `fetchers/orc.py` was built that way.

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

Errors from individual companies do not abort the run — every remaining company is still fetched and the digest is still emailed. They are collected and printed at the end, and the script then exits with a non-zero code if *any* company failed, so a broken board shows up as a red run rather than passing silently.

---

## Project Structure

```
internship-tracker/
├── main.py               # Entry point — orchestrates fetch, diff, notify
├── diff.py               # File-backed deduplication logic (seen_jobs.json)
├── notify.py             # Email formatting and SMTP dispatch
├── companies.json        # List of tracked companies
├── seen_jobs.json        # Dedup ledger — committed back by CI each run
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
│   ├── orc.py            # Oracle Recruiting Cloud (Oracle, Honeywell)
│   ├── amd.py            # AMD Jibe search API (registered, currently unused)
│   ├── icims.py          # iCIMS REST API — NON-FUNCTIONAL, use type "custom" instead
│   └── jina.py           # Jina Reader + Gemini Flash extraction (chunked; free → key 1 → key 2 tiers)
└── .github/
    └── workflows/
        └── run.yml       # GitHub Actions cron definition
```

---

## Tracked Companies

**57 companies**, grouped by the platform each is fetched from. The authoritative
list is [`companies.json`](companies.json) — this table is a snapshot of it.

| Source | Count | Companies |
|---|---:|---|
| **Greenhouse** | 17 | Agility Robotics, Anduril, Anthropic, Apptronik, Bandwidth, Databricks, Epic Games, Figure AI, Katalyst Space, Nuro, Pendo, Relativity Space, Rithum, Rocket Lab, SpaceX, Waymo, Zipline |
| **Custom (Jina + Gemini)** | 16 | Apple, Astrobotic, Cisco, Fidelity Investments, Firefly Aerospace, First Citizens Bank, Google, IBM, Intuitive Machines, Joby Aviation, Lenovo, MetLife, Nutanix, Rivian, SAS, Tesla |
| **Workday** | 11 | Blue Origin, Boston Dynamics, Deutsche Bank, Marvell, Maxar, NVIDIA, Red Hat, Rockwell Automation, S&P Global, Sierra Space, Wolfspeed |
| **Ashby** | 5 | 1X Technologies, OpenAI, Rivian VW Tech, Skydio, Wayve |
| **Oracle Recruiting Cloud** | 2 | Honeywell, Oracle |
| **Phenom** | 2 | Microsoft, Qualcomm |
| **Amazon** | 1 | Amazon |
| **Eightfold** | 1 | NetApp |
| **Lever** | 1 | Zoox |
| **SmartRecruiters** | 1 | Astroscale |

Want one added? [**Request a company here.**](https://forms.gle/coZd4rP7JtiTjFFW6)
Or add it yourself — see [Adding a New Company](#adding-a-new-company).
