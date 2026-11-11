"use client";
import { useState } from "react";
import { ArrowUpRight, Filter } from "lucide-react";
import { ScreenProps } from "@/lib/types";
import { Badge, Empty, caseLabel } from "@/components/ui";
import { title, shortDate } from "@/lib/api";
export function Requests({ data, onCase, search = "" }: ScreenProps) {
  const [status, setStatus] = useState("all");
  const [kind, setKind] = useState("all");
  const rows = data.cases.filter(
    (c) =>
      (status === "all" || c.primary_status === status) &&
      (kind === "all" || c.kind === kind) &&
      [
        c.summary,
        c.order_id,
        c.kind,
        data.conversations.find((x) => x.id === c.conversation_id)
          ?.customer_name,
      ]
        .join(" ")
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <section className="panel requests-panel">
      <div className="table-controls">
        <div className="tabs">
          {["all", "flagged", "ongoing", "resolved"].map((s) => (
            <button
              key={s}
              className={status === s ? "active" : ""}
              onClick={() => setStatus(s)}
            >
              {title(s)}
              <span>
                {s === "all"
                  ? data.cases.length
                  : data.cases.filter((c) => c.primary_status === s).length}
              </span>
            </button>
          ))}
        </div>
        <label className="inline-filter">
          <Filter size={15} />
          <span className="sr-only">Request type</span>
          <select
            aria-label="Request type"
            value={kind}
            onChange={(e) => setKind(e.target.value)}
          >
            <option value="all">All request types</option>
            {Array.from(new Set(data.cases.map((c) => c.kind))).map((k) => (
              <option key={k} value={k}>
                {title(k)}
              </option>
            ))}
          </select>
        </label>
      </div>
      {rows.length ? (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Case / customer</th>
                <th>Request</th>
                <th>Status</th>
                <th>Next step</th>
                <th>Created</th>
                <th>
                  <span className="sr-only">Open</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id}>
                  <td>
                    <button className="cell-link" onClick={() => onCase(c.id)}>
                      {c.order_id || caseLabel(c.id)}
                    </button>
                    <small>
                      {
                        data.conversations.find(
                          (x) => x.id === c.conversation_id,
                        )?.customer_name
                      }
                    </small>
                  </td>
                  <td>
                    <strong>{title(c.kind)}</strong>
                    <small className="truncate">{c.summary}</small>
                  </td>
                  <td>
                    <Badge value={c.primary_status} />
                  </td>
                  <td>{title(c.status)}</td>
                  <td className="subtle">{shortDate(c.created_at)}</td>
                  <td>
                    <button
                      className="icon-button"
                      aria-label={"Open case " + c.id}
                      onClick={() => onCase(c.id)}
                    >
                      <ArrowUpRight size={17} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty
          title="No matching cases"
          text="Try another status, request type, search, or date range."
        />
      )}
    </section>
  );
}
