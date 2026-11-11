"use client";
import { useState } from "react";
import { ShieldCheck, Sparkles, ArrowRight } from "lucide-react";
import { Workspace, Rules, Mutate, Product } from "@/lib/types";
import { Badge, SectionTitle, Modal } from "@/components/ui";
import { money, shortDate, title } from "@/lib/api";
function InventoryItem({
  product,
  mutate,
}: {
  product: Product;
  mutate: Mutate;
}) {
  const [price, setPrice] = useState(product.price_paise / 100),
    [stock, setStock] = useState(product.stock),
    [busy, setBusy] = useState(false);
  return (
    <form
      className="inventory-item"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        try {
          await mutate(
            "/products/" + product.id,
            { price_paise: Math.round(price * 100), stock },
            "PATCH",
          );
        } catch {
        } finally {
          setBusy(false);
        }
      }}
    >
      <div>
        <strong>{product.name}</strong>
        <p>
          {product.reserved_stock} reserved · {product.available_stock}{" "}
          available
        </p>
      </div>
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
        Physical stock
        <input
          type="number"
          min={product.reserved_stock}
          value={stock}
          onChange={(e) => setStock(Number(e.target.value))}
        />
      </label>
      <button className="button" disabled={busy}>
        Save item
      </button>
    </form>
  );
}
export function Policies({
  data,
  mutate,
}: {
  data: Workspace;
  mutate: Mutate;
}) {
  const published = data.policies
    .filter((p) => p.published)
    .sort((a, b) => b.version - a.version)[0];
  const [rules, setRules] = useState<Rules>(published.rules),
    [instruction, setInstruction] = useState(""),
    [busy, setBusy] = useState(false),
    [review, setReview] = useState<string | null>(null);
  const draft = data.policies.find((p) => p.id === review);
  const drafts = data.policies.filter(
    (p) => !p.published && p.version > published.version,
  );
  function field<K extends keyof Rules>(key: K, value: Rules[K]) {
    setRules((r) => ({ ...r, [key]: value }));
  }
  async function act(path: string, body: unknown = {}) {
    setBusy(true);
    try {
      await mutate(path, body);
      return true;
    } catch {
      return false;
    } finally {
      setBusy(false);
    }
  }
  const numbers: {
    key: keyof Rules;
    label: string;
    max: number;
    currency?: boolean;
  }[] = [
    { key: "return_window_days", label: "Return window (days)", max: 365 },
    {
      key: "auto_refund_limit_paise",
      label: "Automatic refund limit (₹ / order)",
      max: 100000,
      currency: true,
    },
    { key: "warranty_days", label: "Warranty period (days)", max: 3650 },
    {
      key: "engraving_paise",
      label: "Engraving fee (₹)",
      max: 10000,
      currency: true,
    },
    {
      key: "gift_wrap_paise",
      label: "Gift wrap fee (₹)",
      max: 10000,
      currency: true,
    },
    { key: "preparation_days", label: "Preparation time (days)", max: 90 },
  ];
  return (
    <>
      <div className="policy-layout">
        <section className="panel">
          <SectionTitle
            title="Automation rules"
            subtitle={
              "Published version " +
              published.version +
              " · " +
              shortDate(published.created_at)
            }
            action={<Badge value="published" />}
          />
          <form
            className="policy-form"
            onSubmit={(e) => {
              e.preventDefault();
              void act("/policies/drafts", rules);
            }}
          >
            <div className="notice">
              <ShieldCheck size={18} />
              <span>
                Edits stay in a draft. Only published rules guide customer
                actions.
              </span>
            </div>
            <h3>What your AI may do</h3>
            <div className="form-grid">
              {(
                [
                  "return_permission",
                  "refund_permission",
                  "redelivery_permission",
                  "customization_permission",
                ] as const
              ).map((key) => (
                <label key={key}>
                  {title(key.replace("_permission", ""))}
                  <select
                    value={rules[key]}
                    onChange={(e) => field(key, e.target.value)}
                  >
                    <option value="automatic">
                      Automatic after customer consent
                    </option>
                    <option value="approval_required">
                      Seller approval required
                    </option>
                    <option value="unavailable">Unavailable</option>
                  </select>
                </label>
              ))}
              <label>
                Store pickup
                <select
                  value={rules.pickup}
                  onChange={(e) => field("pickup", e.target.value)}
                >
                  <option value="allowed">
                    Automatic after customer consent
                  </option>
                  <option value="approval_required">
                    Seller approval required
                  </option>
                  <option value="prohibited">Unavailable</option>
                </select>
              </label>
            </div>
            <h3>Eligibility, prices & timing</h3>
            <div className="form-grid">
              {numbers.map((f) => (
                <label key={f.key}>
                  {f.label}
                  <input
                    type="number"
                    min="0"
                    max={f.max}
                    step={f.currency ? "0.01" : "1"}
                    value={Number(rules[f.key]) / (f.currency ? 100 : 1)}
                    onChange={(e) =>
                      field(
                        f.key,
                        Math.round(
                          Number(e.target.value) * (f.currency ? 100 : 1),
                        ),
                      )
                    }
                  />
                </label>
              ))}
            </div>
            <h3>Eligible return reasons</h3>
            <div className="checkbox-group">
              {["damaged", "defective", "incorrect_item"].map((reason) => (
                <label className="checkbox-label" key={reason}>
                  <input
                    type="checkbox"
                    checked={rules.return_reasons.includes(reason)}
                    onChange={(e) =>
                      field(
                        "return_reasons",
                        e.target.checked
                          ? [...rules.return_reasons, reason]
                          : rules.return_reasons.filter((r) => r !== reason),
                      )
                    }
                  />
                  {title(reason)}
                </label>
              ))}
            </div>
            <div className="checkbox-group vertical">
              {(
                [
                  "require_photo",
                  "require_return_inspection",
                  "cancellation_before_shipping",
                ] as const
              ).map((key) => (
                <label className="checkbox-label" key={key}>
                  <input
                    type="checkbox"
                    checked={rules[key]}
                    onChange={(e) => field(key, e.target.checked)}
                  />
                  {key === "require_photo"
                    ? "Require a clear product photo"
                    : key === "require_return_inspection"
                      ? "Inspect received returns before refunds"
                      : "Allow cancellation before shipping"}
                </label>
              ))}
            </div>
            <p className="helper">
              Engraving requires seller approval. Customer proposals expire
              after 24 hours. Pending and completed refunds count toward the
              order’s remaining paid balance.
            </p>
            <div className="form-actions">
              <button
                type="button"
                className="button"
                onClick={() => setRules(published.rules)}
              >
                Restore published rules
              </button>
              <button className="button primary" disabled={busy}>
                Save policy draft <ArrowRight size={15} />
              </button>
            </div>
          </form>
        </section>
        <aside className="policy-side">
          <section className="panel">
            <SectionTitle
              title="Draft with AI"
              subtitle="Describe the change. Review before publishing."
            />
            <div className="panel-content">
              <label>
                Policy instruction
                <textarea
                  value={instruction}
                  onChange={(e) => setInstruction(e.target.value)}
                  placeholder="For example: change the return window to 10 days."
                />
              </label>
              <button
                className="button full"
                disabled={busy || instruction.trim().length < 5}
                onClick={() => void act("/policies/draft", { instruction })}
              >
                <Sparkles size={16} />
                Create draft
              </button>
              <p className="helper">
                {data.mode.ai === "demo"
                  ? "Local drafting supports simple return-window and refund-limit edits."
                  : "AI drafts are suggestions. Check every value."}
              </p>
            </div>
          </section>
          <section className="panel">
            <SectionTitle
              title="Awaiting publication"
              subtitle={drafts.length + " saved draft(s)"}
            />
            <div className="panel-content">
              {drafts.length ? (
                drafts.map((d) => (
                  <div className="draft-row" key={d.id}>
                    <div>
                      <strong>Version {d.version}</strong>
                      <p>{shortDate(d.created_at)}</p>
                    </div>
                    <button
                      className="button small"
                      onClick={() => setReview(d.id)}
                    >
                      Review
                    </button>
                  </div>
                ))
              ) : (
                <p className="helper">
                  Save a draft to review the changes here.
                </p>
              )}
            </div>
          </section>
          <section className="panel">
            <SectionTitle title="Published history" />
            <div className="panel-content">
              {data.policies
                .filter((p) => p.published)
                .map((p) => (
                  <details className="version-history" key={p.id}>
                    <summary>
                      Version {p.version} · {shortDate(p.created_at)}
                    </summary>
                    <pre>{JSON.stringify(p.rules, null, 2)}</pre>
                  </details>
                ))}
            </div>
          </section>
        </aside>
      </div>
      <details className="panel catalog-panel">
        <summary>
          Catalog & inventory{" "}
          <span>
            {data.products.length} products · prices include tax in the demo
          </span>
        </summary>
        <div className="panel-content">
          {data.products.map((p) => (
            <InventoryItem
              key={p.id + ":" + p.stock + ":" + p.price_paise}
              product={p}
              mutate={mutate}
            />
          ))}
        </div>
      </details>
      {draft && (
        <Modal
          title={"Review policy version " + draft.version}
          onClose={() => setReview(null)}
        >
          <div className="panel-content">
            <p>
              Publishing makes these rules active. Pending customer proposals
              will need fresh review and consent.
            </p>
            <div className="policy-diff">
              {Object.entries(draft.rules)
                .filter(
                  ([key, value]) =>
                    JSON.stringify(value) !==
                    JSON.stringify(published.rules[key as keyof Rules]),
                )
                .map(([key, value]) => (
                  <div key={key}>
                    <strong>{title(key)}</strong>
                    <span>
                      {String(published.rules[key as keyof Rules])} →{" "}
                      <b>{String(value)}</b>
                    </span>
                  </div>
                ))}
            </div>
            {JSON.stringify(draft.rules) ===
              JSON.stringify(published.rules) && (
              <p className="helper">
                These rules have the same values as the published version.
              </p>
            )}
            <details>
              <summary>All proposed values</summary>
              <pre>{JSON.stringify(draft.rules, null, 2)}</pre>
            </details>
            <button
              className="button primary full"
              disabled={busy}
              onClick={async () => {
                if (await act("/policies/" + draft.id + "/publish")) {
                  setRules(draft.rules);
                  setReview(null);
                }
              }}
            >
              Publish version {draft.version}
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
