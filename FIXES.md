## Refactor Issues — 2026-06-03

- [x] `fetchers/__init__.py:14` — `_US_TERMS` includes "remote" and "hybrid" as bare substrings, causing is_us_location() to return True for "Remote — Berlin, Germany", "Hybrid, London, UK", "Remote EMEA", and any non-US location string containing those words
- [x] `fetchers/greenhouse.py`, `fetchers/ashby.py`, `fetchers/icims.py`, `fetchers/amazon.py`, `fetchers/phenom.py`, `fetchers/workday.py` — All six fetchers duplicate the same try/except → RuntimeError pattern; extracted `http_get`/`http_post` helpers into `fetchers/__init__.py`
- [x] `fetchers/workday.py`, `fetchers/amazon.py`, `fetchers/phenom.py` — Offset/limit pagination copy-pasted across three fetchers; extracted `offset_paginate()` generator into `fetchers/__init__.py`
- [x] `diff.py:14-25` — Double-checked locking on `_client` removed; single-threaded cron job needs no thread safety overhead
- [x] `fetchers/icims.py:19-58` — Added Content-Type check before `.json()`; now raises an actionable RuntimeError when iCIMS returns HTML instead of JSON
- [x] `main.py:10` — `load_dotenv()` moved after all imports, eliminating mid-file side-effect
- [x] `fetchers/jina.py:130-132` — Restructured retry loop with `last_exc` variable; dead sentinel `raise` eliminated
- [x] `fetchers/` — HTTP retry added via `requests.Session` + `HTTPAdapter(Retry(...))` in shared `http_get`/`http_post`; covers greenhouse, ashby, icims, workday, amazon, phenom, and jina
- [x] `.github/workflows/run.yml` — `requirements.txt` pinned to exact versions from last successful CI run (supabase==2.30.1, google-genai==2.7.0, resend==2.30.1, requests==2.34.2, python-dotenv==1.2.2)
