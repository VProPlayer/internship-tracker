# To Add

Remaining work for `companies.json` — Triangle-area candidates (RTP / Morrisville / Cary /
Raleigh / Durham).

**Status as of 2026-08-03:** the originally-requested eight are all resolved. Ten new
companies are live in `companies.json`; two are blocked for a concrete technical reason.

---

## Blocked — job listings are JS shells Jina cannot render

These have no fetchable listing page. Their careers sites render job rows client-side, so
`r.jina.ai` returns page chrome with zero postings in it. A `custom` entry for any of them
spends a Jina read plus a Gemini call every run and reliably returns nothing.

- **ERICSSON — removed from `companies.json`.** A full-text scan of its 135,815 rendered
  characters showed the only "intern" matches were the cookie banner, nav links, and
  filter category labels ("Internal Communications", "Internal Controls") — no job rows at
  all. The Eightfold API path is also unavailable: both `app.eightfold.ai` and
  `ericsson.eightfold.ai` return 403 to every client, browser UA included, while NetApp's
  Eightfold host returns 200 from the same machine. Blocked on both routes.

- **TOSHIBA GLOBAL COMMERCE SOLUTIONS** (RTP HQ) — real careers host is
  `careers.commerce.toshiba.com`; the openings page (`/en/openings`) renders as a shell
  with search chrome only, no job rows. Note `careers.toshibacommerce.com`, guessed
  earlier, does not resolve at all.
- **EXTREME NETWORKS** (Morrisville HQ) — `jobs.extremenetworks.com` and
  `careers.extremenetworks.com` both fail to resolve publicly. The only reachable page is
  the marketing page at `extremenetworks.com/about-extreme-networks/career/internships`,
  which lists no requisitions.

**To unblock either:** open the careers page in a browser, filter to internships, and read
the network tab for the XHR that returns job JSON. That endpoint can then be added
directly, the way `fetchers/orc.py` was built from Honeywell's.

## Removed after testing

- **LABCORP** — added, tested, then removed. Its Workday tenant (`labcorp`/wd1/`External`)
  works, but "intern" matches 1545 requisitions of which **zero** are relevant undergrad
  technical roles. It exceeded the 20-page cap on every run, meaning the new truncation
  reporting would email a warning every single run for a company that never yields a
  posting. Burlington is also the outer edge of "Triangle" at ~50 min from RTP.
  Re-add only if `workday.py` gains a per-company `max_pages` override.

## Still worth considering — not yet probed

- **KYNDRYL** (RTP) — IBM infrastructure spinoff, large local site.
- **INFOSYS** (RTP) — high volume, quality varies.
- **BLUE CROSS NC** (Durham) — health data engineering.
- **BAYER CROP SCIENCE** (RTP) — larger software org than the name suggests.
- **ADVANCE AUTO PARTS** (Raleigh) — HQ tech org.
- **UBS** (Raleigh) — took over much of the ex-Credit Suisse Raleigh campus.
- **RELIAS** (Morrisville).
- **CORNING OPTICAL COMMUNICATIONS** (Durham/RTP).

Deliberately excluded: **nCino** (Wilmington), **Duke Energy** / **Truist** (Charlotte),
**Vontier/Gilbarco** (Greensboro) — outside the Triangle.

---

## Open questions unrelated to companies

1. **`fetchers/icims.py` is dead code.** Confirmed non-functional — iCIMS serves HTML, with
   no unauthenticated JSON API. All four iCIMS companies (Rivian, SAS, Joby, First
   Citizens) correctly use the `custom` path instead. The module is still imported and
   registered at `main.py:9,18`. Delete it, or annotate it as non-functional.
2. **`fetchers/amd.py` has no entry in `companies.json`.** Registered in the dispatch table
   but never invoked — a second orphaned fetcher. It works (tested directly, 0 current
   postings); it just has no company pointing at it. Add an AMD entry or drop the module.
3. **Puerto Rico is treated as non-US.** `is_us_country("PR")` returns False, so Honeywell's
   San Juan internship is filtered out. Arguably wrong — PR is US soil and open to US
   students. Changing `_US_COUNTRY_VALUES` would affect every fetcher, so it is left as a
   deliberate decision for you rather than a silent behavior change.
