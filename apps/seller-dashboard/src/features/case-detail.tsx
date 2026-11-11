"use client";
import { useEffect, useState } from "react";
import {
  Check,
  ShieldCheck,
  Clock3,
  ArrowUpRight,
  ImageIcon,
} from "lucide-react";
import { Workspace, CaseRecord, Mutate } from "@/lib/types";
import { Badge, Modal, caseLabel } from "@/components/ui";
import { API_URL, money, shortDate, title } from "@/lib/api";
import { Messages } from "./inbox";
function EvidencePhoto({ id, token }: { id: string; token: string }) {
  const [url, setUrl] = useState("");
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    let object = "";
    fetch(API_URL + "/api/evidence/" + id + "/image", {
      headers: { Authorization: "Bearer " + token },
    })
      .then((r) => {
        if (!r.ok) throw Error();
        return r.blob();
      })
      .then((blob) => {
        object = URL.createObjectURL(blob);
        if (active) setUrl(object);
      })
      .catch(() => setFailed(true));
    return () => {
      active = false;
      if (object) URL.revokeObjectURL(object);
    };
  }, [id, token]);
  return url ? (
    <a href={url} target="_blank" rel="noreferrer">
      <img
        className="evidence-photo"
        src={url}
        alt="Customer product evidence"
      />
    </a>
  ) : (
    <div className="photo-placeholder">
      <ImageIcon />
      {failed ? "Preview unavailable" : "Loading private photo…"}
    </div>
  );
}
export function CaseDetail({
  item,
  data,
  mutate,
  token,
  onClose,
}: {
  item: CaseRecord;
  data: Workspace;
  mutate: Mutate;
  token: string;
  onClose: () => void;
}) {
  const [tab, setTab] = useState("details"),
    [note, setNote] = useState(""),
    [quote, setQuote] = useState(item.quote_paise / 100),
    [days, setDays] = useState(Number(item.details.preparation_days ?? 1)),
    [waive, setWaive] = useState(false),
    [code, setCode] = useState(""),
    [restock, setRestock] = useState(false),
    [busy, setBusy] = useState(false),
    [failure, setFailure] = useState("");
  const [engraving, setEngraving] = useState(
      String(item.details.engraving || ""),
    ),
    [giftWrap, setGiftWrap] = useState(Boolean(item.details.gift_wrap)),
    [slotId, setSlotId] = useState(String(item.details.slot_id || "SLOT-PM"));
  const giftFee = giftWrap
    ? (data.policies.find((p) => p.published)?.rules.gift_wrap_paise ?? 14900)
    : 0;
  const order = data.orders.find((o) => o.id === item.order_id),
    conv = data.conversations.find((c) => c.id === item.conversation_id);
  const evidence = data.evidence.filter((e) => e.case_id === item.id);
  const reservation = data.reservations.find((r) => r.case_id === item.id);
  const returned = data.returns.find((r) => r.case_id === item.id);
  const operations = data.operations.filter((o) => o.case_id === item.id);
  const logs = data.audit_logs.filter(
    (l) => l.entity_id === item.id || l.entity_id === item.proposal_ref,
  );
  async function act(path: string, body: unknown = {}, method = "POST") {
    setBusy(true);
    setFailure("");
    try {
      await mutate(path, body, method);
    } catch (error) {
      setFailure(
        error instanceof Error
          ? error.message
          : "The action could not be completed.",
      );
    } finally {
      setBusy(false);
    }
  }
  function decide(decision: string) {
    return act("/cases/" + item.id + "/decision", {
      decision,
      note,
      quote_paise: Math.round(quote * 100),
      preparation_days: days,
      waive_return: waive,
      engraving,
      gift_wrap: giftWrap,
      slot_id: slotId,
    });
  }
  const pending = [
    "pending_seller",
    "pending_verification",
    "needs_details",
    "expired",
  ].includes(item.status);
  const actionable = [
    "customization",
    "refund",
    "return",
    "replacement",
    "pickup",
    "redelivery",
    "warranty",
    "checkout",
    "cancellation",
  ].includes(item.kind);
  return (
    <Modal
      title={caseLabel(item.id) + " · " + title(item.kind)}
      onClose={onClose}
      drawer
    >
      <div className="case-intro">
        <div>
          <Badge value={item.primary_status} />
          <span className="subtle">{title(item.status)}</span>
        </div>
        <h2>{item.summary}</h2>
        <p>
          {conv?.customer_name} · Opened {shortDate(item.created_at)}
        </p>
      </div>
      <div className="tabs case-tabs">
        {["details", "conversation", "activity"].map((t) => (
          <button
            className={tab === t ? "active" : ""}
            key={t}
            onClick={() => setTab(t)}
          >
            {title(t)}
          </button>
        ))}
      </div>
      <div className="case-body">
        {failure && (
          <div className="error-banner" role="alert">
            {failure}
          </div>
        )}
        {tab === "conversation" && (
          <>
            <div className="inline-between">
              <span>
                {conv?.handoff ? "Store team handling" : "AI assistance"}
              </span>
              <button
                className="button"
                disabled={busy}
                onClick={() =>
                  act(
                    "/conversations/" + item.conversation_id + "/handoff",
                    { enabled: !conv?.handoff },
                    "PATCH",
                  )
                }
              >
                {conv?.handoff ? "Resume AI" : "Take over"}
              </button>
            </div>
            <Messages messages={conv?.messages || []} mutate={mutate} />
            <p className="helper">Open Inbox to reply as the store team.</p>
          </>
        )}
        {tab === "activity" && (
          <div className="activity-list">
            {logs.length ? (
              logs.map((l) => (
                <article key={l.id}>
                  <span className="activity-dot" />
                  <div>
                    <strong>{title(l.action.replaceAll(".", " "))}</strong>
                    <p>
                      {l.actor} · {shortDate(l.created_at)}
                    </p>
                    <details>
                      <summary>Recorded facts</summary>
                      <pre>{JSON.stringify(l.detail, null, 2)}</pre>
                    </details>
                  </div>
                </article>
              ))
            ) : (
              <p>No activity is recorded for this seeded case yet.</p>
            )}
          </div>
        )}
        {tab === "details" && (
          <>
            {item.flag_reason && (
              <div className="case-alert">
                <ShieldCheck size={19} />
                <div>
                  <strong>Why this needs attention</strong>
                  <p>{item.flag_reason}</p>
                </div>
              </div>
            )}
            {Boolean(
              item.details.customer_claim || item.details.ordered_product,
            ) && (
              <section className="case-section">
                <h3>Customer report</h3>
                {Boolean(item.details.customer_claim) && (
                  <p>{String(item.details.customer_claim)}</p>
                )}
                {Boolean(item.details.ordered_product) && (
                  <p>Ordered: {String(item.details.ordered_product)}</p>
                )}
                {Boolean(item.details.received_product) && (
                  <p>Received: {String(item.details.received_product)}</p>
                )}
                {Boolean(item.details.requested_resolution) && (
                  <p>
                    Requested:{" "}
                    {title(String(item.details.requested_resolution))}
                  </p>
                )}
              </section>
            )}
            {Boolean(item.details.verified_store_facts) && (
              <section className="case-section">
                <h3>Verified store facts</h3>
                <dl>
                  {Object.entries(
                    item.details.verified_store_facts as Record<
                      string,
                      unknown
                    >,
                  )
                    .filter(([key]) =>
                      [
                        "order_status",
                        "delivery_status",
                        "product_name",
                        "delivery_location",
                        "proof_of_delivery",
                        "history_available",
                      ].includes(key),
                    )
                    .map(([key, value]) => (
                      <div key={key}>
                        <dt>{title(key)}</dt>
                        <dd>
                          {value == null
                            ? "Not available"
                            : typeof value === "object"
                              ? JSON.stringify(value)
                              : String(value)}
                        </dd>
                      </div>
                    ))}
                </dl>
              </section>
            )}
            {Array.isArray(item.details.conflicting_evidence) &&
              item.details.conflicting_evidence.length > 0 && (
                <section className="case-section">
                  <h3>Conflicting evidence</h3>
                  <ul>
                    {item.details.conflicting_evidence.map((fact, index) => (
                      <li key={index}>{String(fact)}</li>
                    ))}
                  </ul>
                </section>
              )}
            {Boolean(item.details.suggested_action) && (
              <section className="case-section">
                <h3>Next step for the store</h3>
                <p>{String(item.details.suggested_action)}</p>
              </section>
            )}
            {order && (
              <section className="case-section">
                <h3>
                  Order context <span>{order.id}</span>
                </h3>
                <div className="order-summary">
                  <div>
                    <strong>{order.product_name}</strong>
                    <p>
                      {title(order.status)} · {title(order.delivery_status)}
                    </p>
                  </div>
                  <strong>{money(order.total_paise)}</strong>
                </div>
                <div className="facts">
                  <span>
                    Paid <b>{money(order.paid_paise)}</b>
                  </span>
                  <span>
                    Refunded <b>{money(order.refunded_paise)}</b>
                  </span>
                </div>
              </section>
            )}
            <section className="case-section">
              <h3>
                Checks & permissions{" "}
                <span>Policy v{item.policy_version || "—"}</span>
              </h3>
              {item.checks.map((c, i) => (
                <div className="check-row" key={i}>
                  <Check size={15} />
                  <span>{c.label}</span>
                  <small>{c.passed ? "Checked" : "Needs review"}</small>
                </div>
              ))}
              <div className="facts">
                <span>
                  Unsuccessful solutions <b>{item.resolution_attempts} / 2</b>
                </span>
                <span>
                  Seller involvement{" "}
                  <b>{item.seller_assisted ? "Recorded" : "None"}</b>
                </span>
              </div>
            </section>
            {item.proposal_ref && (
              <section className="case-section">
                <h3>
                  Customer proposal <span>{item.proposal_ref}</span>
                </h3>
                <div className="facts">
                  <span>
                    Consent{" "}
                    <b>
                      {item.consented_at ? "Accepted" : "Awaiting confirmation"}
                    </b>
                  </span>
                  <span>
                    Proposal expiry <b>{shortDate(item.expires_at)}</b>
                  </span>
                </div>
                <p className="helper">
                  Approval is separate from customer acceptance and execution.
                </p>
              </section>
            )}
            <section className="case-section">
              <h3>
                Product evidence <span>{evidence.length} photo(s)</span>
              </h3>
              {evidence.length ? (
                evidence.map((e) => (
                  <article className="evidence-card" key={e.id}>
                    <EvidencePhoto id={e.id} token={token} />
                    <div>
                      <strong>{e.filename}</strong>
                      <p>{e.assessment}</p>
                      {e.verified ? (
                        <Badge value="seller_verified" />
                      ) : (
                        <button
                          disabled={busy}
                          className="button"
                          onClick={() => act("/evidence/" + e.id + "/verify")}
                        >
                          Mark photo verified
                        </button>
                      )}
                    </div>
                  </article>
                ))
              ) : (
                <p className="helper">
                  Photos sent through WhatsApp will appear with the relevant
                  case.
                </p>
              )}
            </section>
            {pending && (
              <section className="case-section decision-form">
                <h3>Your decision</h3>
                {item.kind === "customization" && (
                  <>
                    <label>
                      Engraving text
                      <input
                        maxLength={40}
                        value={engraving}
                        onChange={(e) => setEngraving(e.target.value)}
                      />
                    </label>
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={giftWrap}
                        onChange={(e) => setGiftWrap(e.target.checked)}
                      />
                      Include gift wrapping
                    </label>
                  </>
                )}
                {item.kind === "pickup" && (
                  <label>
                    Pickup window
                    <select
                      value={slotId}
                      onChange={(e) => setSlotId(e.target.value)}
                    >
                      {data.slots.map((s) => (
                        <option
                          key={s.id}
                          value={s.id}
                          disabled={
                            s.reserved >= s.capacity ||
                            new Date(s.ends_at) < new Date()
                          }
                        >
                          {s.label} · {s.capacity - s.reserved} spaces
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                {item.kind === "customization" && (
                  <div className="form-grid">
                    <label>
                      Engraving quote (₹)
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={quote}
                        onChange={(e) => setQuote(Number(e.target.value))}
                      />
                    </label>
                    <label>
                      Preparation days
                      <input
                        type="number"
                        min="0"
                        max="90"
                        value={days}
                        onChange={(e) => setDays(Number(e.target.value))}
                      />
                    </label>
                  </div>
                )}
                <label>
                  Reason or question for the customer
                  <textarea
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="Required when rejecting, requesting details, or waiving a return."
                  />
                </label>
                {(item.kind === "refund" || item.details.action === "refund") &&
                  !item.details.return_inspected && (
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={waive}
                        onChange={(e) => setWaive(e.target.checked)}
                      />
                      Waive return inspection for this case; record the reason
                      above.
                    </label>
                  )}
                {item.kind === "customization" && order && (
                  <div className="proposal-preview">
                    <span>Customer proposal preview</span>
                    <strong>
                      {money(
                        order.total_paise + Math.round(quote * 100) + giftFee,
                      )}
                    </strong>
                    <p>
                      Includes {money(Math.round(quote * 100))} engraving and{" "}
                      {money(giftFee)} gift wrap. Preparation: {days} day(s).
                    </p>
                  </div>
                )}
                <p className="helper">
                  Approval sends the proposed terms to WhatsApp. The customer
                  must confirm before execution.
                </p>
                <div className="decision-actions">
                  <button
                    className="button danger"
                    disabled={busy || !note.trim()}
                    onClick={() => decide("reject")}
                  >
                    Reject
                  </button>
                  <button
                    className="button"
                    disabled={busy || !note.trim()}
                    onClick={() => decide("request_details")}
                  >
                    Request information
                  </button>
                  {actionable && (
                    <button
                      className="button primary"
                      disabled={busy || (waive && !note.trim())}
                      onClick={() => decide("approve")}
                    >
                      Approve proposal
                    </button>
                  )}
                </div>
                {!actionable && (
                  <button
                    className="button primary"
                    disabled={busy || !note.trim()}
                    onClick={() =>
                      act("/cases/" + item.id + "/resolve", { note })
                    }
                  >
                    Resolve and notify customer
                  </button>
                )}
              </section>
            )}
            {returned?.status === "awaiting_return" && (
              <section className="case-section decision-form">
                <h3>Return receipt & inspection</h3>
                <p>
                  Record the actual demo inspection before a refund is proposed.
                </p>
                <label>
                  Inspection note
                  <textarea
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                  />
                </label>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={restock}
                    onChange={(e) => setRestock(e.target.checked)}
                  />
                  Inspected item is sellable; return it to available stock.
                </label>
                <div className="decision-actions">
                  <button
                    className="button"
                    disabled={busy || !note.trim() || restock}
                    onClick={() =>
                      act("/cases/" + item.id + "/inspection", {
                        accepted: false,
                        restock: false,
                        note,
                      })
                    }
                  >
                    Reject inspection
                  </button>
                  <button
                    className="button primary"
                    disabled={busy || !note.trim()}
                    onClick={() =>
                      act("/cases/" + item.id + "/inspection", {
                        accepted: true,
                        restock,
                        note,
                      })
                    }
                  >
                    Accept received return
                  </button>
                </div>
              </section>
            )}
            {reservation && (
              <section className="case-section decision-form">
                <h3>
                  Store pickup <Badge value={reservation.status} />
                </h3>
                <p>
                  {data.slots.find((s) => s.id === reservation.slot_id)?.label}
                </p>
                {reservation.status === "reserved" && (
                  <button
                    className="button primary"
                    disabled={busy}
                    onClick={() => act("/pickups/" + reservation.id + "/ready")}
                  >
                    Mark ready
                  </button>
                )}
                {reservation.status === "ready" && (
                  <>
                    <label>
                      Customer’s six-digit collection code
                      <input
                        aria-label="Collection code"
                        inputMode="numeric"
                        maxLength={6}
                        value={code}
                        onChange={(e) =>
                          setCode(e.target.value.replace(/\D/g, ""))
                        }
                      />
                    </label>
                    <button
                      className="button primary"
                      disabled={busy || code.length !== 6}
                      onClick={() =>
                        act("/pickups/" + reservation.id + "/collect", { code })
                      }
                    >
                      Verify code & complete handover
                    </button>
                    <p className="helper">
                      Records the remaining payment as simulated. No real money
                      moves.
                    </p>
                  </>
                )}
                {["reserved", "ready"].includes(reservation.status) && (
                  <button
                    className="text-link danger-text"
                    disabled={busy}
                    onClick={() =>
                      act("/pickups/" + reservation.id + "/cancel")
                    }
                  >
                    Cancel pickup and release holds
                  </button>
                )}
              </section>
            )}
            {!!operations.length && (
              <section className="case-section">
                <h3>Operations</h3>
                {operations.map((o) => (
                  <div className="operation-row" key={o.id}>
                    <span>
                      {title(o.kind)} <small>{o.provider}</small>
                    </span>
                    <Badge value={o.status} />
                  </div>
                ))}
              </section>
            )}
            <div className="inline-between">
              <span className="helper">
                <Clock3 size={14} /> Updated {shortDate(item.updated_at)}
              </span>
              <button className="text-link" onClick={() => setTab("activity")}>
                View activity log <ArrowUpRight size={14} />
              </button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
