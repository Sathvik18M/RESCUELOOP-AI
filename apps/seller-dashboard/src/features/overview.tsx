"use client";
import Link from "next/link";
import {
  ArrowUpRight,
  ArrowRight,
  Check,
  Layers,
  Clock3,
  Flag,
  CheckCircle2,
} from "lucide-react";
import { ScreenProps } from "@/lib/types";
import { Badge, Empty, SectionTitle } from "@/components/ui";
import { title, shortDate } from "@/lib/api";
export function Overview({ data, onCase }: ScreenProps) {
  const m = data.metrics;
  const stats = [
    {
      label: "Total cases",
      value: m.total,
      icon: Layers,
      hint: "Every customer issue",
    },
    {
      label: "Resolved",
      value: m.resolved,
      icon: CheckCircle2,
      hint: "Completed and communicated",
    },
    {
      label: "Ongoing",
      value: m.ongoing,
      icon: Clock3,
      hint: "Moving toward a resolution",
    },
    {
      label: "Flagged for review",
      value: m.flagged,
      icon: Flag,
      hint: "Your decision is needed",
    },
  ];
  const days: string[] = [];
  const cursor = new Date(data.date_range.from + "T00:00:00Z");
  const end = new Date(data.date_range.to + "T00:00:00Z");
  while (cursor <= end) {
    days.push(cursor.toISOString().slice(0, 10));
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  const stride = Math.max(1, Math.ceil(days.length / 14));
  const bins = days
    .filter((_, i) => i % stride === 0)
    .map((day, index) => {
      const selected = data.cases.filter((c) => {
        const d = new Date(c.created_at).toLocaleDateString("en-CA", {
          timeZone: "Asia/Kolkata",
        });
        return (
          d >= day &&
          d <= days[Math.min(days.length - 1, index * stride + stride - 1)]
        );
      });
      return {
        day,
        resolved: selected.filter((c) => c.primary_status === "resolved")
          .length,
        ongoing: selected.filter((c) => c.primary_status === "ongoing").length,
        flagged: selected.filter((c) => c.primary_status === "flagged").length,
      };
    });
  const max = Math.max(
    1,
    ...bins.map((b) => b.resolved + b.ongoing + b.flagged),
  );
  const flagged = data.cases.filter((c) => c.primary_status === "flagged");
  return (
    <>
      <section className="stats-grid" aria-label="Case statistics">
        {stats.map(({ label, value, icon: Icon, hint }, i) => (
          <article className={"stat-card stat-" + i} key={label}>
            <div className="stat-label">
              {label}
              <Icon size={18} />
            </div>
            <strong>{value}</strong>
            <p>{hint}</p>
          </article>
        ))}
      </section>
      <div className="overview-grid">
        <section className="panel chart-panel">
          <SectionTitle
            title="Case activity"
            subtitle="Created in this period · current status"
            action={<span className="subtle">IST</span>}
          />
          <div
            className="chart"
            role="img"
            aria-label={
              m.total
                ? m.resolved +
                  " resolved, " +
                  m.ongoing +
                  " ongoing, " +
                  m.flagged +
                  " flagged cases"
                : "No cases in this date range"
            }
          >
            <div className="chart-lines">
              {[max, Math.round(max / 2), 0].map((v, i) => (
                <div key={i}>
                  <span>{v}</span>
                  <i />
                </div>
              ))}
            </div>
            <div className="chart-columns">
              {bins.map((b, i) => (
                <div
                  className="chart-column"
                  key={b.day}
                  title={
                    b.day +
                    ": " +
                    (b.resolved + b.ongoing + b.flagged) +
                    " cases"
                  }
                >
                  <div className="stack">
                    <i
                      className="flagged-fill"
                      style={{ height: (b.flagged / max) * 100 + "%" }}
                    />
                    <i
                      className="ongoing-fill"
                      style={{ height: (b.ongoing / max) * 100 + "%" }}
                    />
                    <i
                      className="resolved-fill"
                      style={{ height: (b.resolved / max) * 100 + "%" }}
                    />
                  </div>
                  <span>
                    {i % Math.max(1, Math.floor(bins.length / 6)) === 0
                      ? new Date(b.day + "T12:00:00").toLocaleDateString(
                          "en-IN",
                          { day: "numeric", month: "short" },
                        )
                      : ""}
                  </span>
                </div>
              ))}
            </div>
          </div>
          <div className="chart-legend">
            <span>
              <i className="resolved-fill" />
              Resolved
            </span>
            <span>
              <i className="ongoing-fill" />
              Ongoing
            </span>
            <span>
              <i className="flagged-fill" />
              Flagged
            </span>
          </div>
        </section>
        <section className="panel resolution-panel">
          <SectionTitle
            title="Support at a glance"
            subtitle="Measured from saved outcomes"
          />
          <div
            className="donut"
            style={{
              background: m.total
                ? "conic-gradient(#326954 0 " +
                  (m.resolved / m.total) * 100 +
                  "%, #dbb775 " +
                  (m.resolved / m.total) * 100 +
                  "% " +
                  ((m.resolved + m.ongoing) / m.total) * 100 +
                  "%, #cb8271 0)"
                : "#e9ece6",
            }}
          >
            <div>
              <strong>
                {m.resolution_rate === null ? "—" : m.resolution_rate + "%"}
              </strong>
              <span>resolution rate</span>
            </div>
          </div>
          <div className="mini-metric">
            <span>AI share of resolutions</span>
            <strong>
              {m.ai_share === null ? "Not enough data" : m.ai_share + "%"}
            </strong>
          </div>
          <div className="mini-metric">
            <span>Customer rating</span>
            <strong>
              {m.rating === null ? "No ratings" : m.rating + " / 5"}
            </strong>
          </div>
          <Link href="/insights" className="text-link">
            Explore insights <ArrowUpRight size={15} />
          </Link>
        </section>
      </div>
      <section className="panel">
        <SectionTitle
          title="Cases needing attention"
          subtitle="The context is ready. Your decision keeps things moving."
          action={
            <Link className="text-link" href="/requests">
              View requests <ArrowUpRight size={16} />
            </Link>
          }
        />
        {flagged.length ? (
          <div className="attention-list">
            {flagged.slice(0, 5).map((c) => {
              const order = data.orders.find((o) => o.id === c.order_id);
              const conv = data.conversations.find(
                (v) => v.id === c.conversation_id,
              );
              return (
                <button
                  className="attention-row"
                  key={c.id}
                  onClick={() => onCase(c.id)}
                >
                  <span
                    className={
                      "request-icon " + (c.kind === "refund" ? "peach" : "sage")
                    }
                  >
                    <Flag size={19} />
                  </span>
                  <div className="attention-copy">
                    <strong>
                      {c.order_id || "Customer request"}{" "}
                      <span>— {title(c.kind)}</span>
                    </strong>
                    <p>{c.flag_reason}</p>
                    <small>
                      {conv?.customer_name} ·{" "}
                      {order?.product_name || "Store support"}
                    </small>
                  </div>
                  <Badge value={c.primary_status} />
                  <ArrowRight size={18} />
                </button>
              );
            })}
          </div>
        ) : (
          <Empty
            title="All caught up"
            text="Cases requiring your decision will appear here."
          />
        )}
      </section>
      <div className="overview-footnote">
        <Check size={14} /> Statistics come from saved support cases. Demo
        business records are synthetic.
      </div>
    </>
  );
}
