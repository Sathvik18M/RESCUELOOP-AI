"use client";
import { useState } from "react";
import { Sparkles, ShieldCheck, Save, History, ArrowRight } from "lucide-react";
import { Workspace, Mutate, Rules } from "@/lib/types";
import { api, shortDate } from "@/lib/api";
import { Modal, SectionTitle, Badge } from "@/components/ui";

export function Policies({
  data,
  token,
  mutate,
  notify,
}: {
  data: Workspace;
  token: string;
  mutate: Mutate;
  notify: (s: string, e?: boolean) => void;
}) {
  const current = data.policies[0];
  const [rules, setRules] = useState<Rules>(current.rules);
  const [instruction, setInstruction] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  function field<K extends keyof Rules>(key: K, value: Rules[K]) {
    setRules((r) => ({ ...r, [key]: value }));
  }
  async function draft() {
    setBusy(true);
    try {
      const result = await api<{ rules: Rules }>("/policies/draft", token, {
        method: "POST",
        body: JSON.stringify({ instruction }),
      });
      setRules(result.rules);
      notify("Draft ready. Review the fields before publishing.");
    } catch (e) {
      notify(e instanceof Error ? e.message : "Draft failed", true);
    } finally {
      setBusy(false);
    }
  }
  async function publish() {
    setBusy(true);
    try {
      await mutate("/policies/publish", rules);
      setConfirm(false);
    } catch {
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="policy-layout">
      <div>
        <section className="panel policy-assistant">
          <div className="request-icon">
            <Sparkles size={22} />
          </div>
          <div className="grow">
            <h2>Describe the change. Review the rules.</h2>
            <p>
              Draft your store policy in plain language, then check every field.
            </p>
            <div className="inline-input">
              <input
                aria-label="Policy change instruction"
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                placeholder="For example: allow returns within 14 days, refund limit ₹300"
              />
              <button
                className="button primary"
                disabled={busy || instruction.length < 5}
                onClick={draft}
              >
                <Sparkles size={15} />
                Draft changes
              </button>
            </div>
          </div>
        </section>
        <section className="panel">
          <SectionTitle
            title="Store rules"
            subtitle={`Current published version: ${current.version}. Changes below remain a draft until you publish.`}
            action={<Badge value="published" />}
          />
          <div className="policy-form">
            <div className="form-section">
              <h3>Returns & financial approvals</h3>
              <div className="form-grid">
                <label>
                  Return window (days)
                  <input
                    type="number"
                    min="0"
                    max="365"
                    value={rules.return_window_days}
                    onChange={(e) =>
                      field("return_window_days", Number(e.target.value))
                    }
                  />
                </label>
                <label>
                  Automatic refund limit (₹)
                  <input
                    type="number"
                    min="0"
                    value={rules.auto_refund_limit_paise / 100}
                    onChange={(e) =>
                      field(
                        "auto_refund_limit_paise",
                        Math.round(Number(e.target.value) * 100),
                      )
                    }
                  />
                  <small>Includes previous refunds on the same order.</small>
                </label>
                <label>
                  Warranty period (days)
                  <input
                    type="number"
                    min="0"
                    max="3650"
                    value={rules.warranty_days}
                    onChange={(e) =>
                      field("warranty_days", Number(e.target.value))
                    }
                  />
                </label>
              </div>
            </div>
            <div className="form-section">
              <h3>Pickup & fulfillment</h3>
              <div className="form-grid">
                <label>
                  Store pickup
                  <select
                    value={rules.pickup}
                    onChange={(e) => field("pickup", e.target.value)}
                  >
                    <option value="approval_required">
                      Seller approval required
                    </option>
                    <option value="allowed">Allowed automatically</option>
                    <option value="prohibited">Unavailable</option>
                  </select>
                </label>
                <label>
                  Delivery fee (₹)
                  <input
                    type="number"
                    min="0"
                    value={rules.delivery_fee_paise / 100}
                    onChange={(e) =>
                      field(
                        "delivery_fee_paise",
                        Math.round(Number(e.target.value) * 100),
                      )
                    }
                  />
                </label>
                <label>
                  Tax rate (%)
                  <input
                    type="number"
                    min="0"
                    max="100"
                    step="0.01"
                    value={rules.tax_basis_points / 100}
                    onChange={(e) =>
                      field(
                        "tax_basis_points",
                        Math.round(Number(e.target.value) * 100),
                      )
                    }
                  />
                </label>
              </div>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={rules.cancellation_before_shipping}
                  onChange={(e) =>
                    field("cancellation_before_shipping", e.target.checked)
                  }
                />
                Allow cancellation before shipping
              </label>
            </div>
            <div className="policy-note">
              <ShieldCheck size={18} />
              <p>
                Engraving and new special requests require seller approval in
                this release. The AI can draft policies; only you can publish
                them.
              </p>
            </div>
            <button
              className="button primary"
              disabled={busy}
              onClick={() => setConfirm(true)}
            >
              <Save size={16} />
              Review & publish
            </button>
          </div>
        </section>
      </div>
      <aside className="panel policy-history">
        <SectionTitle title="Policy history" />
        <p className="muted">
          Every version stays available for the audit trail.
        </p>
        {data.policies.map((p) => (
          <div className="history-row" key={p.id}>
            <History size={17} />
            <div>
              <strong>Version {p.version}</strong>
              <p>{shortDate(p.created_at)}</p>
            </div>
          </div>
        ))}
      </aside>
      {confirm && (
        <Modal title="Publish these rules?" onClose={() => setConfirm(false)}>
          <div className="modal-body">
            <p>
              This creates policy version {current.version + 1}. Existing
              pending requests will expire and customers will be asked to
              resubmit them under the new rules.
            </p>
            <p className="helper">
              Completed actions and earlier policy versions remain in the audit
              trail.
            </p>
          </div>
          <footer>
            <button className="button" onClick={() => setConfirm(false)}>
              Keep editing
            </button>
            <button
              className="button primary"
              disabled={busy}
              onClick={publish}
            >
              Publish version {current.version + 1}
              <ArrowRight size={15} />
            </button>
          </footer>
        </Modal>
      )}
    </div>
  );
}
