# Internship Tracker

Monitors 21 company careers pages every weekday morning and emails you a digest of new internship postings. No web server, no dashboard — just a Python script and a GitHub Actions cron job.

---

## What It Does

1. Fetches job postings from companies of your choice using their native APIs (Greenhouse, Workday, iCIMS) or, for companies without a structured API, scrapes the careers page via Jina Reader and extracts postings with Gemini Flash.
2. Compares every posting against a Supabase table (`seen_jobs`) to deduplicate across runs.
3. If new postings are found, sends a plain-text email digest via Resend.
4. Runs automatically Monday–Friday at 1:00 AM ET via GitHub Actions. If the run fails entirely, a separate failure alert is sent.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Scheduler | GitHub Actions cron (`0 6 * * 1-5`) |
| Structured APIs | Greenhouse JSON API, Workday CXS API, iCIMS REST API |
| Unstructured sites | Jina Reader (page → plain text) + Gemini Flash (text → structured JSON) |
| Deduplication | Supabase (Postgres) |
| Email | Resend (shared domain `onboarding@resend.dev`) |
| Runtime | Python 3.12, no web framework |

The Gemini model in use is `gemini-3.1-flash-lite`.

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
| `RESEND_API_KEY` | [Resend dashboard](https://resend.com/api-keys) → Create API Key |
| `JINA_API_KEY` | [Jina AI](https://jina.ai/) → API Keys (optional, but recommended — unauthenticated requests are rate-limited) |

### 4. Add Secrets to GitHub Actions

GitHub Actions reads secrets from your repository settings — **not** from your local `.env` file. You must add them manually through the GitHub UI.

In your forked repository, go to **Settings → Secrets and variables → Actions → New repository secret** and add each of the five keys below by their exact names:

| Secret name | Value |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL (e.g. `https://xxxx.supabase.co`) |
| `SUPABASE_KEY` | Your Supabase anon key (starts with `sb_publishable_` on new accounts) |
| `GEMINI_API_KEY` | Your Google AI Studio key |
| `RESEND_API_KEY` | Your Resend API key |
| `JINA_API_KEY` | Your Jina AI key (optional) |

The workflow at `.github/workflows/run.yml` injects these as environment variables at runtime. Your local `.env` file is ignored by GitHub Actions entirely — it only exists for local runs.

### 5. Update the Recipient Email

Open `notify.py` and change the `RECIPIENT` constant at the top of the file to your email address:

```python
RECIPIENT = "you@example.com"
```

Commit and push the change to your fork.

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
RESEND_API_KEY=your-resend-key
JINA_API_KEY=your-jina-key
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
├── notify.py             # Resend email formatting and dispatch
├── companies.json        # List of tracked companies
├── requirements.txt
├── fetchers/
│   ├── greenhouse.py     # Greenhouse JSON API
│   ├── workday.py        # Workday CXS API
│   ├── icims.py          # iCIMS REST API
│   └── jina.py           # Jina Reader + Gemini Flash fallback
└── .github/
    └── workflows/
        └── run.yml       # GitHub Actions cron definition
```
