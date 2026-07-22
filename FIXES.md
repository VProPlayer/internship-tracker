## Refactor Issues — 2026-07-22

- [x] `fetchers/ashby.py`, `fetchers/lever.py`, `fetchers/smartrecruiters.py`, `fetchers/amazon.py` — Four fetchers each hand-rolled their own "is this country the US" check with drifted tuples; `lever` and `smartrecruiters` omitted "united states" entirely and would have silently dropped every US posting had those platforms spelled the country out. Extracted `is_us_country()` into `fetchers/__init__.py` with one canonical set covering two-letter codes, three-letter codes and full names, normalised for case and periods.
- [x] `fetchers/amazon.py` — `str(job.get("id") or job.get("id_icims", ""))` produced `""` when both fields were absent, sending an empty-string primary key into `diff.py`'s `seen_jobs` table where every subsequent such posting would collide and be treated as already-seen. Now falls back to `make_id()`, matching every other fetcher.
- [x] `notify.py` — `_send()` had no retry around the SMTP call, unlike every fetcher's `http_get`/`http_post`. Added 3 attempts with 5s/10s backoff via `SMTP_MAX_ATTEMPTS`. Authentication errors and recipient rejections are re-raised immediately rather than retried — neither self-heals, and repeating a failed login risks a Google lockout.
- [x] `fetchers/jina.py` — Model bumped `gemini-3.1-flash-lite` → `gemini-3.5-flash-lite` (GA) and lifted into a named `GEMINI_MODEL` constant so future bumps are a one-line change.

### Deferred by decision

- [ ] `fetchers/amd.py:1-80`, `main.py:21` — Dead module: registered in `FETCHERS` but no `companies.json` entry uses `"type": "amd"`. Also reimplements pagination by hand instead of using `offset_paginate`. Left in place deliberately; delete or re-wire when AMD is revisited.

### Declined

- `notify.py` — Splitting the module by concern. The ~220-line `_CSS` block is a template living beside its only consumer; separating it buys indirection, not clarity.
- `fetchers/__init__.py` — `_REMOTE_STANDALONE_RE` / `_EXCLUDE_RE` lack test coverage. True, but the repo has no test suite at all; that is a project-level decision, not a refactor item.
- `main.py:39-56` — Uniform exception handling across per-company failures. Distinguishing transient from permanent errors is a feature, not debt.
