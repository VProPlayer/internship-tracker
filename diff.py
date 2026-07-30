import json
import os
from datetime import datetime, timedelta, timezone

# The seen-jobs ledger lives in the repo itself. The GitHub Action commits the
# updated file back after each run, so dedup state persists across runs without
# any external database. Small by design — a few hundred rows.
_HERE = os.path.dirname(os.path.abspath(__file__))
STORE_FILE = os.path.join(_HERE, "seen_jobs.json")

# A row is pruned once its posting has gone unseen for this long. Open postings
# refresh last_seen every run, so only genuinely-closed roles age out. The window
# must exceed the longest plausible fetch gap, or a role that briefly dropped from
# a feed could be pruned and then re-notified when it reappears.
RETENTION_DAYS = 60


def load_ledger() -> dict[str, dict]:
    """Read the ledger as an id-keyed dict. Missing/empty file → empty ledger."""
    try:
        with open(STORE_FILE) as f:
            rows = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return {row["id"]: row for row in rows}


def save_ledger(ledger: dict[str, dict]) -> None:
    """
    Write the ledger back as a sorted list, stable for clean git diffs.

    Writes to a temp file and atomically renames it into place: this ledger is
    the sole source of dedup truth post-Supabase, and a crash mid-write would
    otherwise truncate it and re-notify everything on the next run.
    """
    rows = sorted(ledger.values(), key=lambda r: (r.get("first_seen") or "", r["id"]))
    tmp = f"{STORE_FILE}.tmp"
    with open(tmp, "w") as f:
        json.dump(rows, f, indent=2)
        f.write("\n")
    os.replace(tmp, STORE_FILE)


def reconcile(ledger: dict[str, dict], fetched: list[dict]) -> list[dict]:
    """
    Fold fetched jobs into the ledger in place: insert new ones, refresh the
    mutable fields (last_seen, title, location, url) on ones already seen, then
    prune anything unseen past the retention window. Returns only genuinely-new
    jobs. Does not persist — the caller saves once via save_ledger().
    """
    now = datetime.now(timezone.utc).isoformat()

    new_jobs = []
    for job in fetched:
        existing = ledger.get(job["id"])
        if existing:
            # Keep the ledger a faithful mirror of the live posting. The dedup
            # key is `id`; these fields don't affect it but drift otherwise.
            existing["last_seen"] = now
            existing["title"] = job["title"]
            existing["url"] = job["url"]
            existing["location"] = job.get("location", "")
        else:
            new_jobs.append(job)
            ledger[job["id"]] = {
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "url": job["url"],
                "location": job.get("location", ""),
                "first_seen": now,
                "last_seen": now,
                "notified": False,
            }

    _prune(ledger, now)
    return new_jobs


def _prune(ledger: dict[str, dict], now_iso: str) -> None:
    """Drop rows whose posting hasn't been seen within RETENTION_DAYS."""
    cutoff = datetime.fromisoformat(now_iso) - timedelta(days=RETENTION_DAYS)
    stale = [
        job_id
        for job_id, row in ledger.items()
        if row.get("last_seen") and datetime.fromisoformat(row["last_seen"]) < cutoff
    ]
    for job_id in stale:
        del ledger[job_id]


def mark_notified(ledger: dict[str, dict], job_ids: list[str]) -> None:
    """Flag the given ids as notified in place. Caller saves via save_ledger()."""
    for job_id in job_ids:
        if job_id in ledger:
            ledger[job_id]["notified"] = True
