import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Badge, EmptyState, Loading, PageHeader } from "../components/ui";

export function Models() {
  const { data = [], isLoading } = useQuery({ queryKey: ["models"], queryFn: api.models });
  return (
    <div className="page">
      <PageHeader
        title="Models"
        badges={data.length > 0 && <Badge>{data.length}</Badge>}
        subtitle="Models built here, and models the Excel bridge found in your watched folders."
      />
      {isLoading ? (
        <Loading />
      ) : data.length === 0 ? (
        <EmptyState icon="table" title="No models yet">
          Open a company and press Start coverage to build one from a template, or run the Excel
          bridge's <code>scan</code> to link the models you already keep.
        </EmptyState>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Origin</th>
                <th>File</th>
                <th>Last seen</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.map((m) => (
                <tr key={m.id}>
                  <td>{m.name}</td>
                  <td>
                    <Badge tone={m.origin === "built" ? "accent" : "neutral"}>{m.origin}</Badge>
                  </td>
                  <td className="muted">{m.file_path ?? "-"}</td>
                  <td>{m.last_seen ?? "-"}</td>
                  <td className="num">
                    <Link to={`/models/${m.id}/assumptions`}>Assumptions →</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
