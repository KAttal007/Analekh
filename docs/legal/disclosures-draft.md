# Analekh: Disclosures (draft v0.1, not yet published)

Written for: analysts, and the compliance teams that approve Analekh for their firm.

## 1. Where our data comes from

| Source | What we take | Who it concerns |
|---|---|---|
| NSE published RSS feeds | Filing announcements, for watching new filings | Listed companies |
| NSE published equity lists (CSV) | Company names, symbols, listing changes | Listed and SME companies |
| NSE integrated-filing and results lookup | Results and XBRL filings | Listed companies |
| NSE daily bhavcopy | Closing prices, one file per trading day | Listed companies |
| NSE Indices constituent lists | Sector and index membership | Index companies |
| SEBI public issues (offer documents) | DRHP, RHP and prospectus PDFs | Companies that are not yet listed |

We read only these sources. We do not crawl other pages, and we identify ourselves as Analekh in every request.

Numbers from exchange filings (XBRL) are machine-read from the filer's own file. Numbers from offer-document PDFs are extracted with an AI model and marked as less certain. Each figure keeps a link to the filing it came from.

## 2. What your firm uploads, and what we keep

Your firm may upload:
- Excel models and templates
- Call recordings (transcribed on our servers)
- Documents that your analysts add to a company

What we keep:
- **Originals are never overwritten.** Every write to a model saves a new version, so the earlier file can always be recovered.
- Uploaded files are stored in your firm's own space and nowhere else.
- Only the firm's signed-in users can see them.

What we do not do: we do not use your models, templates, recordings or notes to train any AI model, ours or anyone else's.

Retention and deletion: [CONFIRM: how long model versions and uploads are kept after a firm leaves, and how a firm asks for deletion].

## 3. What Analekh creates, and where it is stored

| Output | What it is | Stored where |
|---|---|---|
| Report drafts (flash, note, initiation) | Text drafts built only from our data and calculations | Your firm's space |
| Q&A answers | Answers to questions on a company | Your firm's space |
| Model change sets | Proposed updates to a model, applied only after the analyst approves them | Your firm's space; each applied change is a new model version |
| Word and PowerPoint files | Files built from the drafts and data | Your firm's space |

Every draft must be reviewed and edited by the analyst before use. Analekh does not publish anything, and nothing is sent outside your firm unless your analyst sends it.

## 4. Where your data is stored

- All data is stored in India, on servers in Oracle Cloud's Mumbai region.
- Each firm has its own address, `<firm>.analekh.in`, and its own space. Data is not shared between firms.
- Analekh is hosted by us. How a firm's space is configured is covered separately when the product is ready.

## 5. AI: which models, and what happens to your data

We are moving all AI work onto open-weight models that run on our own servers in India. No document is sent to an outside AI provider once a job has moved.

> **Our commitment to sovereign, private AI.** Analekh is actively migrating its AI workloads onto open-weight models hosted on our own infrastructure in India. The aim is twofold: to keep your data resident within India at every step, and to guarantee that your proprietary models, templates and research are never used to train anyone else's AI.
>
> **Where we are today.** Four capabilities still call Anthropic's API, which is hosted outside India: report drafts, company Q&A, template label matching, and KPI extraction from offer-document PDFs. When these run, the relevant text is sent to Anthropic under Anthropic's data terms. Each will move to our own servers as it passes our quality checks, and we will update this notice as each one moves. [CONFIRM: Anthropic's current data-retention and no-training terms before publishing.]

Jobs that never use an AI model: Excel builds and syncs, Word and PowerPoint file building, embeddings and call transcription (both run on our servers already).

Note: the local models are smaller than Claude. Each job moves only after it passes our golden test set, and the grounding check blocks any number not found in our data or calculations.

## 6. Terms and conditions

[CONFIRM with counsel. Draft outline only.]

- Who may use Analekh: analysts and staff of a firm that has signed an agreement with us, using their firm's address.
- Your firm is responsible for its analysts' use, for the research its analysts publish, and for complying with the rules that apply to them.
- Analekh is a tool. It processes your firm's data on your firm's instructions. It does not give investment advice.
- Ratings and target prices come from your analysts. Analekh never proposes them.
- Accuracy: Analekh reads public filings and your own models. Data errors in a source filing are passed on as filed, and the analyst is responsible for checking figures before use.
- Availability, support, fees, term, termination and data return: [CONFIRM].
- Liability cap and indemnity: [CONFIRM with counsel].
- Governing law and courts: India, [CONFIRM the city].
- Acceptable use: no attempts to access another firm's space, no scraping, no sharing of sign-in details, no use to make false or misleading public statements.

## 7. Financial reporting and research rules

- **Ind AS and SEBI listing rules.** The company data we read follows Ind AS and the SEBI listing rules. We read it as filed. Where an amount is plainly tagged in the wrong unit, we correct the unit and mark the filing.
- **SEBI Research Analyst Regulations.** These apply to the research analyst at your firm, not to Analekh. Your firm is responsible for its analysts' research, disclosures and compliance. Analekh does not register as, or act as, a research analyst or investment adviser.
- **DPDP Act, 2023.** [CONFIRM with counsel: our role as data processor for each firm, and the firm's role as data fiduciary, under the DPDP Act and its rules as notified. Phased compliance dates to check.]
- **Non-listed companies.** Figures from offer documents are AI-extracted from PDFs, marked as less certain, and must be checked against the document before use in research.

## 8. Cookies

We set one cookie: the sign-in session cookie. It is strictly necessary for signing in and is removed when you sign out. We do not use advertising or analytics cookies. [CONFIRM by reading the code before publishing.]

## 9. Other notices

- **Not investment advice.** Nothing on Analekh is a recommendation to buy, sell or hold any security.
- **Grievance officer.** [NAME, EMAIL, PHONE: required by Indian law; to be appointed before launch.]
- **Security.** Each firm's space is separated from all others. Passwords are stored as hashes, sign-in is limited per address, and connections are encrypted in transit. [CONFIRM the encryption and backup details before publishing.]
- **Contact.** [EMAIL]
- **Last updated:** [DATE]
