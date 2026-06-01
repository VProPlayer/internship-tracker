import os
from datetime import datetime, timezone

from supabase import create_client, Client

TABLE = "seen_jobs"


def get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)


def find_new_jobs(fetched: list[dict]) -> list[dict]:
    """
    Compare fetched jobs against Supabase. Insert new ones, update last_seen
    on existing ones. Returns only the jobs that are genuinely new.
    """
    if not fetched:
        return []

    client = get_client()
    now = datetime.now(timezone.utc).isoformat()

    fetched_ids = [job["id"] for job in fetched]

    # Pull existing IDs in one query
    response = client.table(TABLE).select("id").in_("id", fetched_ids).execute()
    existing_ids = {row["id"] for row in response.data}

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

    if rows_to_insert:
        client.table(TABLE).insert(rows_to_insert).execute()

    if ids_to_update:
        client.table(TABLE).update({"last_seen": now}).in_("id", ids_to_update).execute()

    return new_jobs


def mark_notified(job_ids: list[str]) -> None:
    if not job_ids:
        return
    client = get_client()
    client.table(TABLE).update({"notified": True}).in_("id", job_ids).execute()
