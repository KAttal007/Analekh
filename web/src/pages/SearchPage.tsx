import { Link } from "react-router-dom";

const STEPS = [
  {
    title: "Find any company",
    text: "Search every NSE-listed company by ticker or name. Numbers are collected for every company that files results.",
  },
  {
    title: "Watch or analyse",
    text: "Add a company to your watchlist, or press Analyse, for deep coverage: AI extraction, model updates, reports and alerts.",
  },
  {
    title: "Approve every change",
    text: "Nothing touches your model until you approve it. Every number links back to the filing it came from.",
  },
];

export function SearchPage() {
  return (
    <div className="page">
      <div className="card hero">
        <h1>Every NSE-listed company, from day one</h1>
        <p>
          Start typing in the search bar above, or press <kbd>/</kbd> from anywhere. Results narrow
          with each letter: <code>T</code> lists tickers and names starting with T, <code>TCS</code>{" "}
          finds Tata Consultancy Services.
        </p>
        <div className="actions" style={{ marginTop: 8 }}>
          <Link className="btn btn-primary" to="/watchlist">
            Open watchlist
          </Link>
          <Link className="btn" to="/templates">
            Set up a template
          </Link>
        </div>
      </div>
      <div className="steps">
        {STEPS.map((s, i) => (
          <div key={s.title} className="card step">
            <span className="step-number">{i + 1}</span>
            <h2>{s.title}</h2>
            <p>{s.text}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
