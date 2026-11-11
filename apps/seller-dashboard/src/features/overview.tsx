"use client";
import Link from "next/link";
import {
  ArrowUpRight,
  ArrowRight,
  MessageCircle,
  ShieldCheck,
  Clock3,
  Star,
  Sparkles,
  PackageCheck,
  CircleCheck,
} from "lucide-react";
import { Workspace, CaseRecord } from "@/lib/types";
import { Badge, ProductArt, SectionTitle, Empty } from "@/components/ui";
import { money, shortDate, title } from "@/lib/api";

export function Overview({
  data,
  onReview,
}: {
  data: Workspace;
  onReview: (c: CaseRecord) => void;
}) {
  const pending = data.cases.filter((c) => c.status === "pending_seller");
  const metrics = [
    {
      label: "Active conversations",
      value: data.conversations.length,
      description: "Customers connected to your store",
      icon: MessageCircle,
    },
    {
      label: "Waiting for your approval",
      value: data.metrics.pending,
      description: "A human touch makes the difference",
      icon: Clock3,
    },
    {
      label: "Requests completed",
      value: data.metrics.completed,
      description: "Confirmed actions, saved and tracked",
      icon: ShieldCheck,
    },
    {
      label: "Customer rating",
      value: data.metrics.rating ? `${data.metrics.rating} / 5` : "—",
      description: `From ${data.reviews.length} customer reviews`,
      icon: Star,
    },
  ];
  return (
    <>
      <div className="welcome">
        <div>
          <div className="eyebrow">
            <span className="live-dot" /> YOUR CUSTOMER CARE, CONNECTED
          </div>
          <h2>
            A little attention.
            <br />
            <span>A better customer experience.</span>
          </h2>
          <p>
            Keep conversations moving, review what needs you,
            <br className="desktop-break" /> and let RescueLoop take care of the
            follow-through.
          </p>
          <Link className="button primary" href="/inbox">
            Open your inbox <ArrowUpRight size={17} />
          </Link>
        </div>
        <div className="loop-art" aria-hidden="true">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="orbit orbit-three" />
          <div className="orbit-center">
            <PackageCheck size={38} />
          </div>
          <div className="orbit-node node-one">
            <MessageCircle size={21} />
          </div>
          <div className="orbit-node node-two">
            <ShieldCheck size={21} />
          </div>
          <div className="orbit-note">
            <span className="live-dot" /> Every request, in the loop
          </div>
        </div>
      </div>
      <div className="metrics">
        {metrics.map(({ label, value, description, icon: Icon }) => (
          <div className="metric" key={label}>
            <div className="metric-top">
              <span>{label}</span>
              <Icon size={18} />
            </div>
            <strong>{value}</strong>
            <p>{description}</p>
          </div>
        ))}
      </div>
      <div className="overview-grid">
        <section className="panel">
          <SectionTitle
            title="Needs your attention"
            subtitle="Your decisions keep things moving."
            action={
              <Link className="text-link" href="/approvals">
                View all <ArrowUpRight size={15} />
              </Link>
            }
          />
          {pending.length ? (
            pending.slice(0, 3).map((c) => {
              const order = data.orders.find((o) => o.id === c.order_id);
              return (
                <div className="request-row" key={c.id}>
                  <div
                    className={`request-icon ${c.kind === "refund" ? "orange" : ""}`}
                  >
                    <Sparkles size={20} />
                  </div>
                  <div className="grow">
                    <div className="row-title">
                      {title(c.kind)} request{" "}
                      <span className="mini-tag">{c.order_id}</span>
                    </div>
                    <p>{c.summary}</p>
                    <small>
                      {order?.customer_name} · Policy v{c.policy_version}
                    </small>
                  </div>
                  <button className="button small" onClick={() => onReview(c)}>
                    Review <ArrowRight size={15} />
                  </button>
                </div>
              );
            })
          ) : (
            <Empty
              title="You're all caught up"
              text="New requests that need your decision will appear here."
            />
          )}
          <div className="panel-foot">
            <ShieldCheck size={15} /> Sensitive actions always follow your
            published policies.
          </div>
        </section>
        <section className="panel insight-panel">
          <div className="eyebrow">
            <Sparkles size={15} /> STORE INSIGHTS
          </div>
          <h3>
            Listen. Learn.
            <br />
            Make the next order better.
          </h3>
          {data.insights.slice(0, 2).map((i) => (
            <div className="insight-mini" key={i.title}>
              <span>{i.count}</span>
              <div>
                <strong>{i.title}</strong>
                <p>{i.description}</p>
              </div>
            </div>
          ))}
          <Link className="text-link" href="/insights">
            Explore your insights <ArrowUpRight size={15} />
          </Link>
        </section>
      </div>
      <div className="overview-grid">
        <section className="panel">
          <SectionTitle
            title="Recent orders"
            subtitle="The latest from your store."
            action={
              <Link className="text-link" href="/orders">
                All orders <ArrowUpRight size={15} />
              </Link>
            }
          />
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Product / order</th>
                  <th>Customer</th>
                  <th>Amount</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.orders.map((o) => (
                  <tr key={o.id}>
                    <td>
                      <div className="product-cell">
                        <ProductArt kind={o.product_id} />
                        <div>
                          <strong>{o.product_name}</strong>
                          <small>{o.id}</small>
                        </div>
                      </div>
                    </td>
                    <td>{o.customer_name}</td>
                    <td className="numeric">{money(o.total_paise)}</td>
                    <td>
                      <Badge value={o.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <section className="panel">
          <SectionTitle
            title="Activity, at a glance"
            subtitle="A clear record of every action."
          />
          <div className="timeline">
            {data.audit_logs.slice(0, 4).map((log) => (
              <div className="timeline-item" key={log.id}>
                <span>
                  <CircleCheck size={15} />
                </span>
                <div>
                  <strong>{title(log.action.replaceAll(".", " "))}</strong>
                  <p>
                    {log.actor} · {shortDate(log.created_at)}
                  </p>
                </div>
              </div>
            ))}
          </div>
          <Link className="text-link panel-link" href="/activity">
            View action log <ArrowUpRight size={15} />
          </Link>
        </section>
      </div>
    </>
  );
}
