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

## AI roadmap decisions (owner, 2026-10-30; to brainstorm further before building)

Decided:

- Hosting: a cloud GPU is for the demo only; each firm runs its own hardware in production (AI.md section 5). No Claude API anywhere, for data privacy.
- Demo goal: an end-to-end run ending in a live document the client can view; a queue view with many analysts is the second act.
- Report edits: the final version comes back as edits in the web app; those edits and the accepted reports train the model.
- Hosts: all approved (RBI, Government of India, OPEC, World Bank, WEF, IBEF, CRISIL, EY, McKinsey, BCG, Bain). Paths still to be listed and confirmed per host.
- Ministries: all of them, through an explicit curated host list (no wildcard domains).
- Starting model: skipped until the POC works.
- Analyst adapter: no fixed count; retrain on all accepted reports, go live only if the automatic check passes.
- Embeddings: a local embedder (default); the model is chosen by testing on real filings.

Build order (agreed in principle, to confirm):

1. Model interface (OpenAI-style, works with Ollama and vLLM) and a report queue with fair share across analysts
2. Web editor, version history and Accept button (starts training-data capture)
3. Context sources, `context_documents`, embeddings and the cron jobs
4. Agentic flow: why-questions, estimate diff, conflict flags, drafting
5. Evaluation harness, then the learning loop
6. Demo kit: GPU setup script, load test, cost figures, live-document view

Open: the queue design (concurrency per provider, overflow policy) is to be brainstormed before project 1 starts.

## Redesign: announcements, Notices and company notes (owner, 2026-10-30; next session starts here)

Start with the brainstorming step and write the spec in `docs/superpowers/specs/` before any code. Nothing below is built.

**Why it came up.** The watcher downloaded the PDF behind every announcement and board-meeting feed item. The feed's title is only the company name, so the classifier (`classify_announcement`, `analekh/ingest/pipeline.py`) could not tell announcements apart, and 6,372 files landed as kind `other`: 11.5 GB in 17 days (13 to 30 October), about 20 GB a month, on a disk that reached 80%. None was used: 6,374 stayed `fetched`, 5 were parsed (184 chunks, 0 KPIs).

**Already done (commit `a1ef982`, deployed 2026-10-30).** Only transcripts, presentations and annual reports are downloaded now. Every other announcement is closed without a request and keeps its `feed_items` row (link, title, description). The 6,373 stored `other` files were deleted from MinIO and the database (5 parsed ones kept); the disk is at 31%. Recorded in `docs/design/deviations.md`.

**Owner's idea.**

- Do not download or store these files; link to the NSE URL in the database.
- When the watcher finds a notice, another program reads it and writes a note. A text note per company makes it easier for the agentic AI to draft reports, and the notes show in the web app as notices on a new **Notices** screen.

**What the data looks like (checked on the VM).**

- All files came from `nsearchives.nseindia.com`: 5,174 from the `announcements` feed, 1,203 from `board_meetings`. About 375 a day; average 1.8 MB, largest 89 MB (a 192-page scheme of amalgamation, Arisinfra's creditors' meeting, 23 October).
- The feed `description` carries the subject: "X has informed the Exchange regarding ...", and for board meetings `purpose |Meeting Date: DD-Mon-YYYY`. Some descriptions are blank (2 of 8 sampled).
- File names also carry the subject (`Quick_Financial_Result`, `Analystcallrecording`, `CL-Earnings_call`, `PressRelease`, `Outcome`, `Regulation_30`, `Statement_of_Deviation_and_Variation`, `Utilization_of_issue_proceeds_Certificate`, `Newspaper...`) but are spelled many ways (`bm`, `bmintimation`, `boardmeetingintimation`), so they cannot be the only signal.
- Some announcers are not equity companies (municipal corporations with listed bonds, mutual funds and ETFs).
- The calendar reads `feed_items` of the `board_meetings` feed (`analekh/schedule.py`), never the files. Those rows must stay.
- Kinds still downloaded: 390 transcripts (320 MB), 380 presentations (1.4 GB), 1 annual report, all since 14 to 21 October; IPO documents are stored separately under `ipo/` (542 MB, from SEBI).

**Questions to settle.**

- [ ] Reading without storing: a note needs one download per document, read in memory and discarded. Allow that? Confirm it is covered by rule 1 ("the files they link to" from the RSS feeds).
- [ ] Which subjects get a note (results, board-meeting outcomes, earnings calls, press releases, mergers and schemes, fund raising) and which show only the description line (routine certificates, newspaper clippings, trading-window letters)?
- [ ] Classification: use the feed description (and file name) as well as the title; fix the keyword lists, which see only company names today.
- [ ] Which companies: the whole universe, or the watchlist and deep coverage only? Drop non-equity issuers.
- [ ] Who writes the note: a local model (AI.md) or Claude; cost at about 375 documents a day; grounding (rule 3: only numbers from the document) and no ratings or targets (rule 8); human review?
- [ ] Where the notes live: a database table, or text files per company in object storage (the owner said text files); how they are searched and cited by the report agent.
- [ ] The Notices screen: global feed and per company, filters by subject, link to the NSE PDF; every route needs a signed-in user (rule 9); an alert when a watchlist company has a notice.
- [ ] Do transcripts, presentations and annual reports stay downloaded (they feed KPI extraction), or move to the same read-and-note flow?
- [ ] Delete the 5 parsed `other` files or keep them.
- [ ] Documents to update with it: design doc sections 6.9 (calendar), 9.3 (storage), 17 and 20, `docs/design/deviations.md`, and `Commit-Info.md`.

**Constraints that apply.** CLAUDE.md rules 1 (NSE access only through `PoliteClient`, no widening of `ALLOWED_HOSTS` or `ALLOWED_PATHS` without the owner), 3, 8, 9 and 11; money as Decimal; no raw exchange files in git.

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
- [x] `fail2ban` and `unattended-upgrades` installed and confirmed running (2026-10-30): the `sshd` jail is active (5 tries in 10 minutes, 10-minute ban; 924 failures and 83 bans so far), and the daily upgrade timer ran and is scheduled
- [x] Domain `analekh.in` (GoDaddy India registrar, DNS on Cloudflare) live 2026-10-30: zone active, `analekh.in` and `www` proxied, SSL/TLS Full (strict), Always Use HTTPS on, GoDaddy mail records kept (DNS only). `www` redirects to the domain; `deploy/Caddyfile` keeps the `sslip.io` name as a fallback; `PRODUCTION_URL` is the domain
- [x] Oracle security list: port 443 only from Cloudflare's 15 IPv4 ranges (the all-addresses rule removed); port 80 open (certificate renewals); direct access to the VM on 443 now blocked. Side effect: the `sslip.io` fallback does not answer; to use it, add `0.0.0.0/0` on 443 again in the Oracle console
- [x] The per-address sign-in limit sees the real client address behind Cloudflare, Caddy and nginx (checked 2026-10-30: the owner's phone address appeared in the API log for a failed sign-in)
- [x] Hosting and the NSE-from-cloud finding recorded in `docs/design/deviations.md` and design doc 22.7 (2026-10-27)
- [x] CI on uv's image with `.venv` cached on `uv.lock`, retries and longer timeouts; Docker runner `pull_policy = ["if-not-present"]` (2026-10-27)
- [x] Ubuntu checked: 24.04.5 LTS, no release upgrade needed; routine `apt upgrade` with a backup first

Remaining:

- [x] Backups off the box (2026-10-30): private Oracle Object Storage bucket `analekh-backups` (Mumbai, Oracle keys). The nightly dump is copied there by `~/backup-db.sh` with rclone (instance principal, no stored key); weekly copy of the MinIO files at 03:00 Sundays; dumps deleted after 14 days by a bucket lifecycle rule. Restore test passed: the 17:10 dump restored with no errors and 56,417 filings, against 56,425 live (the gap is the filings added since). Free tier is 20 GiB combined; the account is on a Free Trial, so upgrade before it ends (data in a trial account can be deleted)
- [ ] SSH limited to the owner's address in Oracle's security list (now open to all addresses, key-only, with `fail2ban`). Held back 2026-10-30: the owner's address changes with each network, so a fixed-address rule could lock them out. Options: Oracle Bastion (works from any network, no open port 22) or a VPN such as Tailscale. Done meanwhile: passwords and keyboard-interactive login off, `PermitRootLogin no` (`/etc/ssh/sshd_config.d/99-hardening.conf`), `fail2ban` bans of 1 hour (`/etc/fail2ban/jail.d/sshd-local.conf`)
- [ ] Oracle bucket `analekh-backups`: add a lifecycle rule that deletes `db/` objects after 14 days (console, Object Lifecycle Policy); upgrade the Free Trial account before it ends
- [ ] `node-forge` 1.4.0 (high) in the Excel add-in's dev tooling has no fixed version yet (OSV audit, allowed to fail); `qs` is overridden to 6.16.1 in `pnpm-workspace.yaml`

VM state that is not in the repo (kept on the VM only): `/home/ubuntu/backup-db.sh` (nightly dump, then `rclone copy` to the bucket), the `ubuntu` crontab (nightly 21:30 backup; weekly MinIO copy Sundays 03:00), `~/.config/rclone/rclone.conf` (rclone 1.75.2 in `/usr/local/bin`, instance-principal login; the Ubuntu package is too old), `/etc/analekh/production.env`, the two SSH and `fail2ban` drop-in files above, and the Oracle dynamic group `analekh-vm` with policy `analekh-vm-backups`.
- [ ] Container scanning gives no report on the Arm64 images (allowed to fail: the scanner looks for `linux/amd64`, the images are Arm64). Try `TRIVY_PLATFORM: linux/arm64` on both scanning jobs. Also open: `dependency_audit` flags `qs` 6.16.0 (fixed in 6.16.1) and `node-forge` 1.4.0 (no fix yet)
- [ ] Confirm the first scheduled backup ran: `tail -3 ~/backups/backup.log` on the VM

- [ ] SSH from the college wifi and from Oracle Cloud Shell times out (seen 2026-10-27; the phone hotspot works). Cloud Shell could not reach the VM on 443 either, so check its network setting before relying on it

Suggested order: the off-box backup bucket (with one test restore), SSH access decision, then the scanning decision.

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
