"use client";
import { useState } from "react";
import {
  ArrowRight,
  Check,
  X,
  Package,
  Plus,
  SlidersHorizontal,
} from "lucide-react";
import { Badge, Empty, Modal, ProductArt, SectionTitle } from "@/components/ui";
import { money, shortDate, title } from "@/lib/api";
import { Workspace, CaseRecord, Mutate, Product } from "@/lib/types";

export function Approvals({
  data,
  onReview,
  search,
  refunds = false,
}: {
  data: Workspace;
  onReview: (c: CaseRecord) => void;
  search: string;
  refunds?: boolean;
}) {
  const [filter, setFilter] = useState("all");
  const list = data.cases.filter(
    (c) =>
      (!refunds ||
        ["refund", "return", "replacement", "warranty"].includes(c.kind)) &&
      (filter === "all" || c.status === filter) &&
      `${c.summary} ${c.order_id} ${c.kind}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <section className="panel">
      <SectionTitle
        title={refunds ? "Returns & refunds" : "Approval center"}
        subtitle="Review the facts. Make a decision. We'll follow up with the customer."
      />
      <div className="tabs">
        {["all", "pending_seller", "pending_customer", "completed"].map((f) => (
          <button
            key={f}
            className={filter === f ? "active" : ""}
            onClick={() => setFilter(f)}
          >
            {f === "all" ? "All requests" : title(f)}
            <span>
              {data.cases.filter((c) => f === "all" || c.status === f).length}
            </span>
          </button>
        ))}
      </div>
      {list.length ? (
        <div className="approval-list">
          {list.map((c) => (
            <article key={c.id} className="approval-card">
              <div className="request-icon">
                <Package size={21} />
              </div>
              <div className="grow">
                <div className="row-title">
                  {title(c.kind)} <Badge value={c.status} />
                </div>
                <h3>{c.summary}</h3>
                <p>
                  {c.order_id} ·{" "}
                  {data.orders.find((o) => o.id === c.order_id)?.customer_name}{" "}
                  · {shortDate(c.created_at)}
                </p>
                <small>
                  Policy v{c.policy_version}
                  {c.kind === "refund"
                    ? ` · Requested ${money(Number(c.details.amount_paise || 0))}`
                    : ""}
                </small>
              </div>
              <button className="button" onClick={() => onReview(c)}>
                {c.status === "pending_seller"
                  ? "Review request"
                  : "View details"}
                <ArrowRight size={16} />
              </button>
            </article>
          ))}
        </div>
      ) : (
        <Empty
          title="No requests here"
          text="Requests matching this view will appear as customers get in touch."
        />
      )}
    </section>
  );
}

export function DecisionModal({
  item,
  data,
  mutate,
  onClose,
}: {
  item: CaseRecord;
  data: Workspace;
  mutate: Mutate;
  onClose: () => void;
}) {
  const [quote, setQuote] = useState(
    item.kind === "customization" ? "199" : "0",
  );
  const [note, setNote] = useState("");
  const [days, setDays] = useState(1);
  const [busy, setBusy] = useState(false);
  const order = data.orders.find((o) => o.id === item.order_id);
  async function decide(decision: string) {
    setBusy(true);
    try {
      await mutate(`/cases/${item.id}/decision`, {
        decision,
        quote_paise: Math.round(Number(quote) * 100),
        note,
        preparation_days: days,
      });
      onClose();
    } catch {
    } finally {
      setBusy(false);
    }
  }
  const actionable = ["pending_seller", "needs_details"].includes(item.status);
  return (
    <Modal title={`${title(item.kind)} request`} onClose={onClose}>
      <div className="modal-body">
        <div className="detail-top">
          <Badge value={item.status} />
          <span>{item.order_id}</span>
        </div>
        <h3>{item.summary}</h3>
        <p className="muted">
          {order?.customer_name} · {order?.product_name}
        </p>
        <dl className="details">
          <div>
            <dt>Request ID</dt>
            <dd className="mono">{item.id}</dd>
          </div>
          <div>
            <dt>Policy</dt>
            <dd>Version {item.policy_version}</dd>
          </div>
          <div>
            <dt>Expires</dt>
            <dd>{shortDate(item.expires_at)}</dd>
          </div>
          {Object.entries(item.details)
            .filter(([, v]) => v !== false && v !== null)
            .map(([k, v]) => (
              <div key={k}>
                <dt>{title(k)}</dt>
                <dd>{k.endsWith("paise") ? money(Number(v)) : String(v)}</dd>
              </div>
            ))}
        </dl>
        {actionable && (
          <>
            <div className="form-grid">
              {item.kind === "customization" && (
                <label>
                  Engraving / additional quote (₹)
                  <input
                    type="number"
                    min="0"
                    max="100000"
                    step="0.01"
                    value={quote}
                    onChange={(e) => setQuote(e.target.value)}
                  />
                </label>
              )}
              <label>
                Preparation time (days)
                <input
                  type="number"
                  min="0"
                  max="90"
                  value={days}
                  onChange={(e) => setDays(Number(e.target.value))}
                />
              </label>
            </div>
            <label>
              Message to the customer
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Add context, instructions, or a reason for your decision"
                maxLength={1000}
              />
            </label>
            <p className="helper">
              Approval sends a proposal to the customer. They must confirm
              before the action is executed.
            </p>
          </>
        )}
      </div>
      <footer>
        {actionable ? (
          <>
            <button
              className="button danger"
              disabled={busy}
              onClick={() => decide("reject")}
            >
              <X size={16} />
              Reject
            </button>
            <button
              className="button"
              disabled={busy || !note.trim()}
              onClick={() => decide("request_details")}
            >
              Ask for details
            </button>
            <button
              className="button primary"
              disabled={busy}
              onClick={() => decide("approve")}
            >
              <Check size={16} />
              Approve
            </button>
          </>
        ) : (
          <button className="button" onClick={onClose}>
            Close
          </button>
        )}
      </footer>
    </Modal>
  );
}

export function Orders({ data, search }: { data: Workspace; search: string }) {
  const [selected, setSelected] = useState<string | null>(null);
  const order = data.orders.find((o) => o.id === selected);
  const list = data.orders.filter((o) =>
    `${o.id} ${o.customer_name} ${o.product_name}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  return (
    <>
      <section className="panel">
        <SectionTitle
          title="Your orders"
          subtitle="Products, customers, and fulfillment in one place."
        />
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Order / product</th>
                <th>Customer</th>
                <th>Total</th>
                <th>Fulfillment</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {list.map((o) => (
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
                  <td>{title(o.delivery_status)}</td>
                  <td>
                    <Badge value={o.status} />
                  </td>
                  <td>
                    <button
                      className="icon-button"
                      aria-label={`View ${o.id}`}
                      onClick={() => setSelected(o.id)}
                    >
                      <ArrowRight size={17} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!list.length && (
          <Empty title="No matching orders" text="Try a different search." />
        )}
      </section>
      {order && (
        <Modal title={order.id} onClose={() => setSelected(null)}>
          <div className="modal-body">
            <ProductArt kind={order.product_id} large />
            <h3>{order.product_name}</h3>
            <p>{order.customer_name}</p>
            <dl className="details">
              <div>
                <dt>Total</dt>
                <dd>{money(order.total_paise)}</dd>
              </div>
              <div>
                <dt>Simulated payment</dt>
                <dd>{money(order.paid_paise)}</dd>
              </div>
              <div>
                <dt>Refunded</dt>
                <dd>{money(order.refunded_paise)}</dd>
              </div>
              <div>
                <dt>Fulfillment</dt>
                <dd>{title(order.delivery_status)}</dd>
              </div>
            </dl>
            <h4>Customizations</h4>
            {order.customizations.length ? (
              order.customizations.map((c, i) => (
                <p key={i}>
                  {String(c.engraving || c.special_request || "Gift wrapping")}
                  {c.gift_wrap ? " · Gift wrapped" : ""}
                </p>
              ))
            ) : (
              <p className="muted">No customizations accepted yet.</p>
            )}
          </div>
          <footer>
            <button className="button" onClick={() => setSelected(null)}>
              Close
            </button>
          </footer>
        </Modal>
      )}
    </>
  );
}

export function Products({
  data,
  search,
  mutate,
}: {
  data: Workspace;
  search: string;
  mutate: Mutate;
}) {
  const [editing, setEditing] = useState<Product | null>(null);
  const [price, setPrice] = useState(0);
  const [stock, setStock] = useState(0);
  const [busy, setBusy] = useState(false);
  async function save() {
    if (!editing) return;
    setBusy(true);
    try {
      await mutate(
        `/products/${editing.id}`,
        { price_paise: Math.round(price * 100), stock },
        "PATCH",
      );
      setEditing(null);
    } catch {
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="product-grid">
        {data.products
          .filter((p) => p.name.toLowerCase().includes(search.toLowerCase()))
          .map((p) => (
            <article className="panel product-card" key={p.id}>
              <ProductArt kind={p.id} large />
              <div className="product-card-body">
                <div className="eyebrow">{p.category}</div>
                <h2>{p.name}</h2>
                <p>{p.description}</p>
                <div className="product-price">
                  <strong>{money(p.price_paise)}</strong>
                  <Badge value={p.stock > 0 ? "in_stock" : "sold_out"} />
                </div>
                <div className="stock-line">
                  <span>{p.stock} units available</span>
                  <span>{p.id}</span>
                </div>
                <button
                  className="button full"
                  onClick={() => {
                    setEditing(p);
                    setPrice(p.price_paise / 100);
                    setStock(p.stock);
                  }}
                >
                  <SlidersHorizontal size={15} />
                  Edit price & stock
                </button>
              </div>
            </article>
          ))}
      </div>
      {editing && (
        <Modal title={`Edit ${editing.name}`} onClose={() => setEditing(null)}>
          <div className="modal-body form-grid">
            <label>
              Price (₹)
              <input
                type="number"
                min="0"
                step="0.01"
                value={price}
                onChange={(e) => setPrice(Number(e.target.value))}
              />
            </label>
            <label>
              Available stock
              <input
                type="number"
                min="0"
                step="1"
                value={stock}
                onChange={(e) => setStock(Number(e.target.value))}
              />
            </label>
          </div>
          <footer>
            <button className="button" onClick={() => setEditing(null)}>
              Cancel
            </button>
            <button
              className="button primary"
              disabled={
                busy || price < 0 || stock < 0 || !Number.isInteger(stock)
              }
              onClick={save}
            >
              Save changes
            </button>
          </footer>
        </Modal>
      )}
    </>
  );
}

export function Pickups({ data, mutate }: { data: Workspace; mutate: Mutate }) {
  const [collect, setCollect] = useState<string | null>(null);
  const [code, setCode] = useState("");
  async function complete() {
    try {
      await mutate(`/pickups/${collect}/collect`, { code });
      setCollect(null);
      setCode("");
    } catch {}
  }
  return (
    <>
      <div className="slot-grid">
        {data.slots.map((s) => (
          <div className="panel slot" key={s.id}>
            <span className="eyebrow">COLLECTION WINDOW</span>
            <h2>{s.label}</h2>
            <p>{s.location}</p>
            <div className="capacity-track">
              <div style={{ width: `${(s.reserved / s.capacity) * 100}%` }} />
            </div>
            <small>
              {s.reserved} of {s.capacity} slots reserved
            </small>
          </div>
        ))}
      </div>
      <section className="panel">
        <SectionTitle
          title="Pickup reservations"
          subtitle="Mark orders ready, then verify the customer's private collection code."
        />
        {data.reservations.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Pickup window</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {data.reservations.map((r) => (
                  <tr key={r.id}>
                    <td>{r.order_id}</td>
                    <td>{data.slots.find((s) => s.id === r.slot_id)?.label}</td>
                    <td>
                      <Badge value={r.status} />
                    </td>
                    <td>
                      {r.status === "reserved" ? (
                        <button
                          className="button small"
                          onClick={() =>
                            mutate(`/pickups/${r.id}/ready`, {}).catch(() => {})
                          }
                        >
                          Mark ready
                        </button>
                      ) : r.status === "ready" ? (
                        <button
                          className="button small"
                          onClick={() => setCollect(r.id)}
                        >
                          Verify collection
                        </button>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title="No pickups reserved yet"
            text="Reservations appear after the customer accepts an eligible pickup request."
          />
        )}
      </section>
      {collect && (
        <Modal title="Verify collection" onClose={() => setCollect(null)}>
          <div className="modal-body">
            <label>
              Customer's six-digit code
              <input
                value={code}
                onChange={(e) =>
                  setCode(e.target.value.replace(/\D/g, "").slice(0, 6))
                }
                inputMode="numeric"
                autoComplete="off"
                maxLength={6}
              />
            </label>
            <p className="helper">
              Ask the customer to show the code received in their conversation.
            </p>
          </div>
          <footer>
            <button
              className="button primary"
              disabled={code.length !== 6}
              onClick={complete}
            >
              Confirm handover
            </button>
          </footer>
        </Modal>
      )}
    </>
  );
}
