"use client";
import { useEffect, useState } from "react";
import {
  Star,
  Sparkles,
  ShieldCheck,
  Download,
  ImageIcon,
  CheckCircle2,
  Unplug,
} from "lucide-react";
import { Workspace, Mutate } from "@/lib/types";
import { API_URL, shortDate, title } from "@/lib/api";
import { Badge, Empty, SectionTitle, Modal } from "@/components/ui";

function PrivateImage({ id, token }: { id: string; token: string }) {
  const [url, setUrl] = useState("");
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let url = "";
    let cancelled = false;
    fetch(`${API_URL}/api/evidence/${id}/image`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (!r.ok) throw Error();
        return r.blob();
      })
      .then((b) => {
        url = URL.createObjectURL(b);
        if (!cancelled) setUrl(url);
        else URL.revokeObjectURL(url);
      })
      .catch(() => setFailed(true));
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [id, token]);
  return url ? (
    <img src={url} alt="Customer-provided product evidence" />
  ) : (
    <div className="image-placeholder">
      <ImageIcon />
      {failed ? "Image unavailable" : "Loading private image…"}
    </div>
  );
}
export function EvidenceGallery({
  data,
  token,
}: {
  data: Workspace;
  token: string;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const item = data.evidence.find((e) => e.id === selected);
  return (
    <>
      {data.evidence.length ? (
        <div className="evidence-grid">
          {data.evidence.map((e) => (
            <button
              className="panel evidence-card"
              key={e.id}
              onClick={() => setSelected(e.id)}
            >
              <PrivateImage id={e.id} token={token} />
              <div>
                <h3>{e.filename}</h3>
                <p>{e.assessment}</p>
                <small>{shortDate(e.created_at)}</small>
              </div>
            </button>
          ))}
        </div>
      ) : (
        <section className="panel">
          <Empty
            title="A clearer picture starts here"
            text="Photos sent through WhatsApp or the demo inbox will appear with their assessment and conversation."
          />
        </section>
      )}
      {item && (
        <Modal title="Customer evidence" onClose={() => setSelected(null)}>
          <div className="modal-body evidence-detail">
            <PrivateImage id={item.id} token={token} />
            <h3>Assessment</h3>
            <p>{item.assessment}</p>
            <p className="helper">
              Image evidence supports review. It does not authorize a refund.
            </p>
          </div>
        </Modal>
      )}
    </>
  );
}

export function Feedback({
  data,
  search,
}: {
  data: Workspace;
  search: string;
}) {
  return (
    <div className="review-grid">
      {data.reviews
        .filter((r) =>
          `${r.body} ${r.topic}`.toLowerCase().includes(search.toLowerCase()),
        )
        .map((r) => (
          <article className="panel review" key={r.id}>
            <div className="review-top">
              <div className="stars">
                {[1, 2, 3, 4, 5].map((n) => (
                  <Star
                    key={n}
                    size={17}
                    fill={n <= r.rating ? "currentColor" : "none"}
                  />
                ))}
              </div>
              <span className="mini-tag">
                {r.source === "demo" ? "Sample review" : r.source}
              </span>
            </div>
            <blockquote>“{r.body}”</blockquote>
            <div className="review-author">
              <div className="avatar">{r.author[0]}</div>
              <div>
                <strong>{r.author}</strong>
                <p>{data.products.find((p) => p.id === r.product_id)?.name}</p>
              </div>
            </div>
            <span className="topic-tag">{r.topic}</span>
          </article>
        ))}
    </div>
  );
}

export function Insights({
  data,
  mutate,
}: {
  data: Workspace;
  mutate: Mutate;
}) {
  const [busy, setBusy] = useState(false);
  const report = data.merchant.settings.insight_report;
  async function analyze() {
    setBusy(true);
    try {
      await mutate("/insights/analyze", {});
    } catch {
    } finally {
      setBusy(false);
    }
  }
  const total = data.cases.length;
  const counts = [
    "pending_seller",
    "pending_customer",
    "completed",
    "rejected",
  ].map((status) => ({
    status,
    count: data.cases.filter((c) => c.status === status).length,
  }));
  return (
    <>
      <div className="insight-intro">
        <Sparkles size={22} />
        <div>
          <h2>Small signals. Useful next steps.</h2>
          <p>
            Insights reflect the records in this workspace. Sample reviews
            remain labeled as demo data.
          </p>
        </div>
        <button className="button primary" disabled={busy} onClick={analyze}>
          {busy ? "Analyzing…" : "Analyze feedback"}
        </button>
      </div>
      {report && (
        <section className="panel" style={{ marginBottom: 22 }}>
          <SectionTitle
            title={
              report.mode === "demo" ? "Demo analysis" : "AI feedback analysis"
            }
            subtitle={`Generated ${shortDate(report.generated_at)}`}
          />
          <div style={{ padding: "0 23px 23px" }}>
            <p>{report.summary}</p>
            <ul
              style={{ paddingLeft: 20, listStyleType: "disc", marginTop: 12 }}
            >
              {report.recommendations.map((item) => (
                <li key={item} style={{ marginTop: 8 }}>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}
      <div className="report-grid">
        <section className="panel">
          <SectionTitle
            title="Request outcomes"
            subtitle={`${total} requests recorded`}
          />
          <div className="bar-chart">
            {counts.map((c, i) => (
              <div key={c.status}>
                <span>{title(c.status)}</span>
                <div className="bar-track">
                  <div
                    style={{
                      width: `${total ? (c.count / total) * 100 : 0}%`,
                      background: ["#d8ae63", "#7c9b8f", "#2b6453", "#cf8581"][
                        i
                      ],
                    }}
                  />
                </div>
                <strong>{c.count}</strong>
              </div>
            ))}
          </div>
        </section>
        <section className="panel">
          <SectionTitle
            title="Customer feedback themes"
            subtitle={`${data.reviews.length} source reviews`}
          />
          <div className="insight-cards">
            {data.insights.map((i) => (
              <div key={i.title}>
                <span className="insight-count">{i.count}</span>
                <div>
                  <h3>{i.title}</h3>
                  <p>{i.description}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
      <div className="policy-note">
        <ShieldCheck size={18} />
        <p>
          Recommendations are advisory. Changes to policies, inventory, and
          customer actions require the appropriate approval.
        </p>
      </div>
    </>
  );
}

export function Activity({
  data,
  search,
}: {
  data: Workspace;
  search: string;
}) {
  const logs = data.audit_logs.filter((l) =>
    `${l.action} ${l.actor} ${l.entity_id}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  function download() {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(logs, null, 2)], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "rescueloop-audit-log.json";
    link.click();
    URL.revokeObjectURL(url);
  }
  return (
    <section className="panel">
      <SectionTitle
        title="Action log"
        subtitle="Saved decisions, actor identities, and execution outcomes. Latest 100 events."
        action={
          <button className="button small" onClick={download}>
            <Download size={15} />
            Export JSON
          </button>
        }
      />
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Action</th>
              <th>Actor</th>
              <th>Record</th>
              <th>Time</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((l) => (
              <tr key={l.id}>
                <td>
                  <span className="log-action">
                    <CheckCircle2 size={15} />
                    {title(l.action.replaceAll(".", " "))}
                  </span>
                </td>
                <td>{l.actor}</td>
                <td className="mono truncate-cell" title={l.entity_id}>
                  {l.entity_id}
                </td>
                <td className="nowrap">{shortDate(l.created_at)}</td>
                <td>
                  <details>
                    <summary>Inspect</summary>
                    <pre>{JSON.stringify(l.detail, null, 2)}</pre>
                  </details>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!logs.length && (
        <Empty title="No matching actions" text="Try a different search." />
      )}
    </section>
  );
}

export function Settings({
  data,
  mutate,
}: {
  data: Workspace;
  mutate: Mutate;
}) {
  const [name, setName] = useState(data.merchant.name);
  const [location, setLocation] = useState(
    data.merchant.settings.location || "",
  );
  const [email, setEmail] = useState(
    data.merchant.settings.support_email || "",
  );
  const [busy, setBusy] = useState(false);
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await mutate(
        "/settings",
        { name, location, support_email: email },
        "PATCH",
      );
    } catch {
    } finally {
      setBusy(false);
    }
  }
  const connections = [
    {
      name: "AI reasoning",
      detail:
        data.mode.ai === "demo"
          ? "Deterministic demo scenarios"
          : "OpenAI Responses API",
      connected: data.mode.ai === "openai",
    },
    {
      name: "WhatsApp",
      detail: data.mode.whatsapp
        ? "Credentials configured; verify delivery with a test message"
        : "Connect credentials to enable live messaging",
      connected: data.mode.whatsapp,
    },
    {
      name: "Evidence storage",
      detail:
        data.mode.storage === "supabase"
          ? "Supabase private bucket"
          : "Private local demo storage",
      connected: true,
    },
  ];
  return (
    <div className="settings-layout">
      <section className="panel">
        <SectionTitle
          title="Store profile"
          subtitle="The details your team uses to support customers."
        />
        <form className="settings-form" onSubmit={save}>
          <label>
            Store name
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              minLength={2}
            />
          </label>
          <label>
            Store location
            <input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              required
              minLength={2}
            />
          </label>
          <label>
            Support email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <button className="button primary" disabled={busy}>
            Save profile
          </button>
        </form>
      </section>
      <section className="panel">
        <SectionTitle
          title="Connections"
          subtitle="Configuration status for this environment."
        />
        {connections.map((c) => (
          <div className="connection-row" key={c.name}>
            {c.connected ? <CheckCircle2 size={20} /> : <Unplug size={20} />}
            <div>
              <h3>{c.name}</h3>
              <p>{c.detail}</p>
            </div>
          </div>
        ))}
        <div className="panel-foot">
          Connection credentials are managed on the backend.
        </div>
      </section>
    </div>
  );
}
