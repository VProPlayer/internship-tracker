import os
import threading
from datetime import datetime, timezone
from typing import Generator

from supabase import create_client, Client

TABLE = "seen_jobs"

# Supabase/PostgREST enforces URL length limits; large `.in_()` lists and bulk
# inserts can silently fail or be rejected beyond this size.
BATCH_SIZE = 200

_client: Client | None = None
_client_lock = threading.Lock()


def _get_client() -> Client:
    """Return a cached Supabase client; thread-safe via double-checked locking."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:  # re-check after acquiring the lock
                _client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    return _client


def _chunks(lst: list, size: int) -> Generator[list, None, None]:
    """Yield successive fixed-size chunks from lst."""
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def find_new_jobs(fetched: list[dict]) -> list[dict]:
    """
    Compare fetched jobs against Supabase. Insert new ones, update last_seen
    on existing ones. Returns only the jobs that are genuinely new.
    """
    if not fetched:
        return []

    client = _get_client()
    now = datetime.now(timezone.utc).isoformat()

    fetched_ids = [job["id"] for job in fetched]

    # SELECT in batches to stay within URL length limits
    existing_ids: set[str] = set()
    for batch in _chunks(fetched_ids, BATCH_SIZE):
        response = client.table(TABLE).select("id").in_("id", batch).execute()
        existing_ids.update(row["id"] for row in response.data)

    new_jobs = []
    rows_to_insert = []
    ids_to_update = []

    for job in fetched:
        if job["id"] in existing_ids:
            ids_to_update.append(job["id"])
        else:
            new_jobs.append(job)
            rows_to_insert.append({
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "url": job["url"],
                "location": job.get("location", ""),
                "first_seen": now,
                "last_seen": now,
                "notified": False,
            })

    # INSERT in batches
    for batch in _chunks(rows_to_insert, BATCH_SIZE):
        client.table(TABLE).insert(batch).execute()

    # UPDATE in batches
    for batch in _chunks(ids_to_update, BATCH_SIZE):
        client.table(TABLE).update({"last_seen": now}).in_("id", batch).execute()

    return new_jobs


def mark_notified(job_ids: list[str]) -> None:
    if not job_ids:
        return
    client = _get_client()
    for batch in _chunks(job_ids, BATCH_SIZE):
        client.table(TABLE).update({"notified": True}).in_("id", batch).execute()
