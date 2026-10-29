# Pending items

Open work, checked against CLAUDE.md ("Where the skeleton stops") and the model-locks work.
Last reviewed 2026-10-27. The plan and order of work are in [roadmap.md](roadmap.md).
Tick a box when it is done. Items marked *status unknown* have not been confirmed.

## Owner actions

- [ ] Two-browser check for model locks: lock and 423, read-only view, toast and chime, stale apply refusal, blocked-filing pop-up, idle and sign-in reminders
- [ ] Confirm Update drafts from the newest non-blocked filing (the rule we built)
- [ ] Review section 8 of `docs/superpowers/specs/2026-10-22-auth-roles-locks-design.md` (model locks)
- [ ] Golden set: run `uv run analekh golden-sheet`, mark the filings against the results PDFs, then `golden-import` and `golden-test`

## Data and mapping

- [x] Sector mapping: index list importer run (2026-10-16): NSE's own sector for 1,430 companies; `data/sector_map.csv` holds overrides only
- [ ] LSEG-to-NSE sector mapping (25 groups to decide) and the 169 companies with no sector
- [x] SME list path confirmed (580 companies; two-digit-year dates parsed)
- [ ] Fill `universe/data/nifty500.csv` (backfill priority list, still empty)
- [ ] Verify XBRL element names marked `# verify` in `xbrl/elements.py` against real filings; run `analekh revalidate` after changes
- [ ] Map the insurers' balance sheet (not mapped yet)

## Templates and backfill

- [ ] Balance sheet and cash flow in `templates_builtin/specs.py` (currently P&L and KPIs only); needs the annual backfill

## Pipeline and GenAI

- [ ] Wire V10 (XBRL wins over AI-extracted values) into `docs/pipeline.py`
- [ ] Confirm the embeddings provider (open question 28.7; a local embedder is built and is the default)
- [ ] Local AI stack ([AI.md](../AI.md)): Ollama on the VM and the laptop, speeds recorded, Tailscale link, provider switch in `genai/client.py` with a `local_llm` queue, golden-set gate per job
- [x] Owner decision: SEBI host for offer documents ([roadmap.md](roadmap.md) 4.1): approved 2026-10-28
- [ ] Owner decision: NSE paths for announcements and debt filings (4.2, 4.3)
- [x] Offer documents: abridged prospectus not used (not every company files one); SEBI's website terms accepted by the owner 2026-10-29 (no API, open access)
- [x] Offer documents: row layout of the RHP (smid 11) and Prospectus (smid 12) lists confirmed by a live fetch of Jio Platforms Limited on 2026-10-29 ([design](superpowers/specs/2026-10-29-ipo-coverage-design.md))
- [ ] IPO coverage: first real run (`analekh ipo-watch`, then `analekh ipo-read`) on the Jio Platforms RHP and Prospectus; hand-check the figures against the PDFs; the owner's marked figures become a golden case
- [ ] IPO coverage: call `ipo.symbols.link_listed` after the daily prices so listed issues pick up their symbol (built and tested, not yet scheduled)
- [ ] IPO coverage: Word export of the draft with the rating and rationale placeholders (not built)
- [ ] Unprocessed feed items: about 290 items from issuers outside the universe (mostly debt-only or unlisted) are never picked up, since the queue needs a matched company. They inflate the "unprocessed" column in `admin/app.py`. Proposed: count only matched items there and leave the rest in "unlinked" (not decided). Review the list in `out/unmatched_feed_items.csv` for companies worth adding to the universe

## Valuation

- [ ] Source debt and cash for `ib/comps.py` so EV multiples are filled in
- [ ] Map insurers' book value for `ib/comps.py`

## Architecture

- [ ] Move reports from inline API execution to Celery jobs, storing files in object storage

## Hosting and operations (Oracle Cloud, Mumbai)

Done:

- [x] Arm64 VM on the free tier (4 OCPU, 24 GB, Ubuntu 24.04), public subnet, ports 80 and 443 open
- [x] NSE reachability from the VM: integrated-filing API, RSS feeds and bhavcopy answer (the home page does not; the app never requests it)
- [x] GitLab runners on the VM: shell runner tagged `india` (Arm64 image builds, deploy) and a Docker runner for the untagged jobs; GitLab's shared runners off, so no compute minutes are used
- [x] Production stack deployed from GitLab (`deploy_production`): API, worker, beat, web, Postgres, Valkey, MinIO, recalc, Caddy with HTTPS on an `sslip.io` host name
- [x] `/etc/analekh/production.env` made by `deploy/make-production-env.sh`; the owner keeps a copy off the server
- [x] Database restored from the laptop (counts match; Alembic at `0012`); the migrate step exits 0 after the image fix
- [x] Nightly `pg_dump` on the VM at 03:00 IST, checked readable, 7 days kept (`~/backup-db.sh`, cron)
- [x] Object-storage files copied from the laptop to the server's MinIO (59,366 files, 4.5 GB, same count and ownership as the source); an iXBRL filing opens from the company page on the server
- [x] `fail2ban` and `unattended-upgrades` installed (service status still to be confirmed)
- [x] Hosting and the NSE-from-cloud finding recorded in `docs/design/deviations.md` and design doc 22.7 (2026-10-27)
- [x] CI on uv's image with `.venv` cached on `uv.lock`, retries and longer timeouts; Docker runner `pull_policy = ["if-not-present"]` (2026-10-27)
- [x] Ubuntu checked: 24.04.5 LTS, no release upgrade needed; routine `apt upgrade` with a backup first

Remaining:

- [ ] Backups off the box: a private Oracle Object Storage bucket (20 GB free) with the nightly dump copied there, plus a weekly copy of the MinIO files; test one restore into a scratch database
- [ ] SSH limited to the owner's address in Oracle's security list (now open to all addresses, key-only)
- [ ] Check that the per-address sign-in limit sees the real client address behind Caddy and nginx (code check; otherwise one address could lock everyone out, or the limit does nothing)
- [ ] Domain name and Cloudflare in front (the `sslip.io` name cannot be proxied); then allow ports 80 and 443 only from Cloudflare's ranges
- [ ] Container scanning gives no report on the Arm64 images (allowed to fail); decide how to scan them
- [ ] Confirm `fail2ban` and `unattended-upgrades` are running: `systemctl is-active fail2ban`, `sudo fail2ban-client status sshd`, `systemctl list-timers apt-daily-upgrade.timer --no-pager`
- [ ] Confirm the first scheduled backup ran: `tail -3 ~/backups/backup.log` on the VM

- [ ] SSH from the college wifi and from Oracle Cloud Shell times out (seen 2026-10-27; the phone hotspot works). Cloud Shell could not reach the VM on 443 either, so check its network setting before relying on it

Suggested order: the sign-in client-address check (security), SSH limited to the owner's address, the off-box backup bucket, then the domain with Cloudflare and the scanning decision.

## Disclosures and legal (draft in `docs/legal/disclosures-draft.md`)

No lawyer yet; revisit when one is found. Nothing here goes live before then.

- [ ] Counsel review of the whole draft before any firm sees it
- [ ] Terms and conditions: fees, term and termination, data return, liability cap, indemnity, governing law and city
- [ ] DPDP Act 2023 and its rules: each firm's role as data fiduciary and Analekh's as processor; phased compliance dates
- [ ] Retention and deletion periods for uploads, model versions and recordings; how a firm asks for deletion
- [ ] Appoint and name a grievance officer (name, email, phone)
- [ ] Confirm Anthropic's current data-retention and no-training terms for the four Claude jobs, until they move to local models
- [ ] Cookie line: read the code and confirm the sign-in cookie is the only one
- [ ] Security paragraph: confirm encryption and backup details against what is deployed
- [ ] Update the AI section as each Claude job moves to a local model (report drafts, Q&A, label matching, PDF KPI extraction)

## Status unknown (confirm)

- [ ] Whether any of the items above were finished outside this session
