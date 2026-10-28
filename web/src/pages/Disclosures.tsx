import { Link } from "react-router-dom";

const SOURCES: [string, string][] = [
  ["NSE published RSS feeds", "Filing announcements, to watch for new filings"],
  ["NSE published equity lists", "Company names, symbols and listing changes"],
  ["NSE integrated-filing and results lookup", "Results and XBRL filings of listed companies"],
  ["NSE daily bhavcopy", "Closing prices, one file per trading day"],
  ["NSE Indices constituent lists", "Sector and index membership"],
  ["SEBI public issues", "DRHP, RHP and prospectus PDFs of companies not yet listed"],
];

const OUTPUTS: [string, string][] = [
  ["Report drafts (flash, note, initiation)", "Built only from our data and calculations"],
  ["Q&A answers", "Answers to questions on a company"],
  ["Model change sets", "Proposed model updates, applied only once the analyst approves"],
  ["Word and PowerPoint files", "Built from the drafts and data"],
];

export function Disclosures() {
  return (
    <div className="legal">
      <Link to="/welcome" className="legal-back">
        ← Back
      </Link>
      <h1>Mandatory Disclosures</h1>
      <p className="legal-draft" role="note">
        Draft, pending legal review. Items in [square brackets] are not yet settled.
      </p>

      <h2>1. Where our data comes from</h2>
      <table className="legal-table">
        <tbody>
          {SOURCES.map(([a, b]) => (
            <tr key={a}>
              <th scope="row">{a}</th>
              <td>{b}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>
        We read only these sources, never crawl other pages, and identify ourselves as Analekh in every request. Numbers from exchange filings (XBRL) are read from the filer's own file. Numbers from
        offer-document PDFs are extracted with an AI model and marked as less certain. Each figure keeps a link to the filing it came from.
      </p>

      <h2>2. What your firm uploads, and what we keep</h2>
      <p>Your firm may upload Excel models and templates, call recordings (transcribed on our servers) and documents added to a company.</p>
      <ul>
        <li>Originals are never overwritten. Every write to a model saves a new version.</li>
        <li>Uploads are stored in your firm's own space and visible only to its signed-in users.</li>
        <li>We do not use your models, templates, recordings or notes to train any AI model, ours or anyone else's.</li>
        <li>Retention and deletion: [how long uploads and model versions are kept after a firm leaves, and how a firm asks for deletion].</li>
      </ul>

      <h2>3. What Analekh creates, and where it is stored</h2>
      <table className="legal-table">
        <tbody>
          {OUTPUTS.map(([a, b]) => (
            <tr key={a}>
              <th scope="row">{a}</th>
              <td>{b}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>
        All outputs are stored in your firm's own space. Every draft must be reviewed and edited by the analyst before use. Analekh publishes nothing, and nothing leaves your firm unless your analyst
        sends it.
      </p>

      <h2>4. Where your data is stored</h2>
      <p>
        All data is stored in India, on servers in Oracle Cloud's Mumbai region. Each firm has its own address, <code>&lt;firm&gt;.analekh.in</code>, and its own space. Data is never shared between
        firms.
      </p>

      <h2>5. AI</h2>
      <p>
        <strong>Our commitment to sovereign, private AI.</strong> Analekh is actively migrating its AI workloads onto open-weight models hosted on our own infrastructure in India. The aim is twofold:
        to keep your data resident within India at every step, and to guarantee that your proprietary models, templates and research are never used to train anyone else's AI.
      </p>
      <p>
        <strong>Where we are today.</strong> Four capabilities still call Anthropic's API, which is hosted outside India: report drafts, company Q&amp;A, template label matching, and KPI extraction
        from offer-document PDFs. When these run, the relevant text is sent to Anthropic under Anthropic's data terms. Each will move to our own servers as it passes our quality checks, and we will
        update this notice as each one moves.
      </p>

      <h2>6. Terms and conditions</h2>
      <ul>
        <li>Analekh is used by analysts and staff of a firm that has an agreement with us, using their firm's address.</li>
        <li>Your firm is responsible for its analysts' use, for the research they publish and for the rules that apply to them.</li>
        <li>Analekh is a tool. It processes your firm's data on your firm's instructions and gives no investment advice.</li>
        <li>Ratings and target prices come from your analysts. Analekh never proposes them.</li>
        <li>Source filings are passed on as filed. The analyst is responsible for checking figures before use.</li>
        <li>Not allowed: reaching another firm's space, scraping, sharing sign-in details, or using Analekh to make false or misleading public statements.</li>
        <li>[Fees, term and termination, data return, liability, indemnity, governing law and courts.]</li>
      </ul>

      <h2>7. Financial reporting and research rules</h2>
      <ul>
        <li>Company data follows Ind AS and the SEBI listing rules. We read it as filed. Where an amount is plainly tagged in the wrong unit, we correct the unit and mark the filing.</li>
        <li>The SEBI Research Analyst Regulations apply to your firm's research analysts, not to Analekh. Analekh does not act as a research analyst or investment adviser.</li>
        <li>Digital Personal Data Protection Act, 2023: [roles of each firm and of Analekh, and the applicable dates].</li>
        <li>Figures from offer documents are AI-extracted from PDFs and must be checked against the document before use in research.</li>
      </ul>

      <h2>8. Cookies</h2>
      <p>We set one cookie: the sign-in session cookie. It is strictly necessary to sign in and is removed when you sign out. We use no advertising or analytics cookies.</p>

      <h2>9. Other notices</h2>
      <ul>
        <li>Not investment advice. Nothing on Analekh is a recommendation to buy, sell or hold any security.</li>
        <li>Grievance officer: [name, email, phone].</li>
        <li>Security: each firm's space is separate. Passwords are stored as hashes, sign-in attempts are limited per address, and connections are encrypted in transit.</li>
        <li>Contact: [email]. Last updated: [date].</li>
      </ul>
    </div>
  );
}
