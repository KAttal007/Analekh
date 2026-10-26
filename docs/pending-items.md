# Pending items

Open work, checked against CLAUDE.md ("Where the skeleton stops") and the model-locks work.
Tick a box when it is done. Items marked *status unknown* have not been confirmed.

## Owner actions

- [ ] Two-browser check for model locks: lock and 423, read-only view, toast and chime, stale apply refusal, blocked-filing pop-up, idle and sign-in reminders
- [ ] Confirm Update drafts from the newest non-blocked filing (the rule we built)
- [ ] Review section 8 of `docs/superpowers/specs/2026-10-22-auth-roles-locks-design.md` (model locks)
- [ ] Golden set: run `uv run analekh golden-sheet`, mark the filings against the results PDFs, then `golden-import` and `golden-test`

## Data and mapping

- [ ] Sector mapping: run the index list importer (`universe/sectors.py`); `data/sector_map.csv` holds overrides only
- [ ] SME list path: confirm it in `universe/loader.py`
- [ ] Fill `universe/data/nifty500.csv` (backfill priority list, still empty)
- [ ] Verify XBRL element names marked `# verify` in `xbrl/elements.py` against real filings; run `analekh revalidate` after changes
- [ ] Map the insurers' balance sheet (not mapped yet)

## Templates and backfill

- [ ] Balance sheet and cash flow in `templates_builtin/specs.py` (currently P&L and KPIs only); needs the annual backfill

## Pipeline and GenAI

- [ ] Wire V10 (XBRL wins over AI-extracted values) into `docs/pipeline.py`
- [ ] Decide the embeddings provider (open question 28.7)
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

Remaining:

- [ ] Backups off the box: a private Oracle Object Storage bucket (20 GB free) with the nightly dump copied there, plus a weekly copy of the MinIO files; test one restore into a scratch database
- [ ] SSH limited to the owner's address in Oracle's security list (now open to all addresses, key-only)
- [ ] Check that the per-address sign-in limit sees the real client address behind Caddy and nginx (code check; otherwise one address could lock everyone out, or the limit does nothing)
- [ ] Domain name and Cloudflare in front (the `sslip.io` name cannot be proxied); then allow ports 80 and 443 only from Cloudflare's ranges
- [ ] Record the hosting and the NSE-from-cloud finding in `docs/design/deviations.md` (design doc 22.7)
- [ ] Container scanning gives no report on the Arm64 images (allowed to fail); decide how to scan them
- [ ] Confirm `fail2ban` and `unattended-upgrades` are running: `systemctl is-active fail2ban`, `sudo fail2ban-client status sshd`, `systemctl list-timers apt-daily-upgrade.timer --no-pager`
- [ ] Confirm the first scheduled backup ran: `tail -3 ~/backups/backup.log` on the VM

Suggested order: the sign-in client-address check (security), SSH limited to the owner's address, the off-box backup bucket, then the domain with Cloudflare, the deviations entry and the scanning decision.

## Status unknown (confirm)

- [ ] Whether any of the items above were finished outside this session
