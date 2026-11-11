"use client";
import { useState } from "react";
import Link from "next/link";
import { Sparkles, ArrowUpRight, Star } from "lucide-react";
import { Workspace, Mutate } from "@/lib/types";
import { SectionTitle, Empty, Badge, caseLabel } from "@/components/ui";
import { shortDate } from "@/lib/api";
export function Insights({
  data,
  mutate,
  onCase,
}: {
  data: Workspace;
  mutate: Mutate;
  onCase: (id: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const reports = data.reports.filter(
    (r) =>
      r.date_from === data.date_range.from && r.date_to === data.date_range.to,
  );
  const report = reports[0];
  async function generate() {
    setBusy(true);
    try {
      await mutate("/insights/analyze", {
        date_from: data.date_range.from,
        date_to: data.date_range.to,
      });
    } catch {
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="insight-intro">
        <span className="insight-symbol">
          <Sparkles size={23} />
        </span>
        <div>
          <h2>Small signals. Useful next steps.</h2>
          <p>Recommendations grounded in the cases behind the numbers.</p>
        </div>
        <button className="button primary" disabled={busy} onClick={generate}>
          {busy ? "Analyzing…" : "Generate insights"}
        </button>
      </div>
      <div className="insight-metrics">
        <article>
          <span>Resolution rate</span>
          <strong>
            {data.metrics.resolution_rate === null
              ? "—"
              : data.metrics.resolution_rate + "%"}
          </strong>
          <p>Resolved / all cases in this period</p>
        </article>
        <article>
          <span>AI share of resolutions</span>
          <strong>
            {data.metrics.ai_share === null ? "—" : data.metrics.ai_share + "%"}
          </strong>
          <p>Resolved cases without seller intervention</p>
        </article>
        <article>
          <span>Median time to resolution</span>
          <strong>
            {data.metrics.median_resolution_hours === null
              ? "—"
              : data.metrics.median_resolution_hours + "h"}
          </strong>
          <p>Includes waiting and reopened time</p>
        </article>
        <article>
          <span>Customer satisfaction</span>
          <strong>
            {data.metrics.rating === null ? "—" : data.metrics.rating + " / 5"}
          </strong>
          <p>
            {data.metrics.review_count} case rating(s) · one active rating per
            case
          </p>
        </article>
      </div>
      <div className="insights-grid">
        <section className="panel">
          <SectionTitle
            title="Customer themes"
            subtitle="Recurring means three or more distinct cases."
          />
          <div className="panel-content">
            {data.insights.length ? (
              data.insights.map((i) => (
                <article className="theme-row" key={i.topic}>
                  <span className="theme-count">{i.count}</span>
                  <div>
                    <h3>{i.title}</h3>
                    <p>{i.description}</p>
                    <div className="source-links">
                      {i.case_ids.map((id) => (
                        <button key={id} onClick={() => onCase(id)}>
                          {caseLabel(id)}
                          <ArrowUpRight size={12} />
                        </button>
                      ))}
                    </div>
                  </div>
                  {i.recurring && <Badge value="recurring" />}
                </article>
              ))
            ) : (
              <Empty
                title="No themes yet"
                text="Saved case feedback will appear here."
              />
            )}
          </div>
        </section>
        <section className="panel">
          <SectionTitle
            title="Customer feedback"
            subtitle="Ratings and comments linked to resolved cases."
          />
          <div className="panel-content">
            {data.reviews.length ? (
              data.reviews.map((r) => (
                <article className="review-row" key={r.id}>
                  <div className="inline-between">
                    <strong>{r.author}</strong>
                    <span className="stars">
                      <Star size={13} fill="currentColor" /> {r.rating} / 5
                    </span>
                  </div>
                  <p>{r.body}</p>
                  <div className="inline-between">
                    <small>
                      {r.source === "demo"
                        ? "Synthetic review"
                        : "Customer feedback"}
                    </small>
                    <button
                      className="text-link"
                      onClick={() => onCase(r.case_id)}
                    >
                      {caseLabel(r.case_id)}
                      <ArrowUpRight size={13} />
                    </button>
                  </div>
                </article>
              ))
            ) : (
              <Empty
                title="No ratings yet"
                text="Customer feedback is requested after resolution."
              />
            )}
          </div>
        </section>
      </div>
      <section className="panel report-panel">
        <SectionTitle
          title="Evidence-backed recommendations"
          subtitle={
            report
              ? "Generated " +
                shortDate(report.generated_at) +
                " · " +
                (report.mode === "demo" ? "Local analysis" : "AI analysis")
              : "Generate a report for the selected date range."
          }
          action={
            report ? (
              <Badge
                value={
                  report.mode === "demo" ? "local_verification" : "available"
                }
              />
            ) : null
          }
        />
        {report ? (
          <div className="panel-content">
            <p className="report-summary">{report.body.summary}</p>
            {report.body.recommendations.length ? (
              report.body.recommendations.map((r, i) => (
                <article className="recommendation" key={i}>
                  <span className="recommendation-number">0{i + 1}</span>
                  <div>
                    <h3>{r.text}</h3>
                    <p>{r.tradeoff}</p>
                    <div className="source-links">
                      {r.case_ids.map((id) => (
                        <button key={id} onClick={() => onCase(id)}>
                          {caseLabel(id)}
                          <ArrowUpRight size={12} />
                        </button>
                      ))}
                      <span>
                        {r.count} distinct case(s)
                        {r.recurring ? " · Recurring" : ""}
                      </span>
                    </div>
                    <button
                      className="text-link"
                      disabled={busy}
                      onClick={async () => {
                        setBusy(true);
                        try {
                          await mutate("/policies/draft", {
                            instruction:
                              r.text +
                              " Consider this suggestion as a draft only.",
                          });
                        } catch {
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      Create policy draft <ArrowUpRight size={14} />
                    </button>
                  </div>
                </article>
              ))
            ) : (
              <p className="helper">
                There is not enough recurring evidence to recommend a policy
                change.
              </p>
            )}
            <p className="helper">
              Recommendations never change rules automatically. Review drafts in{" "}
              <Link className="text-link" href="/policies">
                Policies
              </Link>
              .
            </p>
          </div>
        ) : (
          <Empty
            title="A fresh perspective, when you need it"
            text="Generate insights to save a report with linked source cases. Metrics above update independently."
          />
        )}
      </section>
    </>
  );
}
