"use client";
import { useEffect, useRef, useState } from "react";
import {
  Send,
  Paperclip,
  UserRound,
  ShieldCheck,
  MessageCircle,
  ChevronDown,
  FlaskConical,
} from "lucide-react";
import { Workspace, Mutate } from "@/lib/types";
import { api, shortDate } from "@/lib/api";
import { Badge, Empty } from "@/components/ui";

export function Inbox({
  data,
  token,
  mutate,
  refresh,
  notify,
  search,
}: {
  data: Workspace;
  token: string;
  mutate: Mutate;
  refresh: () => Promise<void>;
  notify: (text: string, error?: boolean) => void;
  search: string;
}) {
  const [selected, setSelected] = useState(data.conversations[0]?.id || "");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [role, setRole] = useState("customer");
  const end = useRef<HTMLDivElement>(null);
  const upload = useRef<HTMLInputElement>(null);
  const conv = data.conversations.find((c) => c.id === selected);
  const order = data.orders.find((o) => o.id === conv?.order_id);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [conv?.messages.length, selected]);
  async function send(value = text) {
    if (!value.trim() || !conv || busy) return;
    setBusy(true);
    try {
      await mutate(
        role === "customer"
          ? `/demo/conversations/${conv.id}/messages`
          : `/conversations/${conv.id}/reply`,
        { text: value, message_id: crypto.randomUUID() },
      );
      setText("");
    } catch {
    } finally {
      setBusy(false);
    }
  }
  async function attach(file: File) {
    if (!conv) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      await api(`/demo/conversations/${conv.id}/evidence`, token, {
        method: "POST",
        body: form,
      });
      await refresh();
      notify("Photo saved for review");
    } catch (e) {
      notify(e instanceof Error ? e.message : "Upload failed", true);
    } finally {
      setBusy(false);
    }
  }
  const suggestions =
    conv?.order_id === "ORD1043"
      ? [
          "Can I collect the wallet tomorrow afternoon?",
          "I want to checkout",
          "5 stars, lovely gift wrapping!",
        ]
      : [
          "Redelivery please. Address: 12 Demo Road, Bengaluru",
          "My headphones arrived damaged",
          "I want a refund",
        ];
  return (
    <div className="inbox">
      <aside className="conversation-list">
        <div className="conversation-heading">
          <h2>Conversations</h2>
          <span>{data.conversations.length}</span>
        </div>
        {data.conversations
          .filter((c) =>
            `${c.customer_name} ${c.order_id}`
              .toLowerCase()
              .includes(search.toLowerCase()),
          )
          .map((c) => (
            <button
              className={`conversation ${selected === c.id ? "selected" : ""}`}
              key={c.id}
              onClick={() => {
                setSelected(c.id);
                setText("");
                setRole(c.channel === "demo" ? "customer" : "seller");
              }}
            >
              <span className="avatar">
                {c.customer_name
                  .split(" ")
                  .map((s) => s[0])
                  .slice(0, 2)
                  .join("")}
              </span>
              <div>
                <strong>{c.customer_name}</strong>
                <p>{c.messages.at(-1)?.body || "No messages yet"}</p>
                <small>
                  {c.order_id || "No order selected"} ·{" "}
                  {c.handoff ? "Human support" : "AI assistance"}
                </small>
              </div>
            </button>
          ))}
        <div className="inbox-foot">
          <ShieldCheck size={16} />
          <span>Conversations stay with their store.</span>
        </div>
      </aside>
      {conv ? (
        <>
          <section className="chat">
            <header className="chat-header">
              <div className="avatar">{conv.customer_name.charAt(0)}</div>
              <div className="grow">
                <h2>{conv.customer_name}</h2>
                <p>
                  <span className="live-dot" />
                  {conv.handoff
                    ? "Seller is handling this conversation"
                    : "RescueLoop assistance active"}
                </p>
              </div>
              <button
                className="button small"
                onClick={() =>
                  mutate(
                    `/conversations/${conv.id}/handoff`,
                    { enabled: !conv.handoff },
                    "PATCH",
                  ).catch(() => {})
                }
              >
                <UserRound size={15} />
                {conv.handoff ? "Return to AI" : "Take over"}
              </button>
            </header>
            {conv.channel === "demo" && (
              <div className="demo-strip">
                <FlaskConical size={15} /> Demo conversation · Messages stay in
                this workspace
              </div>
            )}
            <div className="messages">
              <div className="chat-day">Conversation history</div>
              {conv.messages.map((m) => (
                <div
                  key={m.id}
                  className={`message ${m.role === "customer" ? "incoming" : "outgoing"}`}
                >
                  <span className="message-author">
                    {m.role === "customer"
                      ? conv.customer_name
                      : m.role === "seller"
                        ? "You"
                        : "RescueLoop"}
                  </span>
                  <p>{m.body}</p>
                  <small>
                    {new Date(m.created_at).toLocaleTimeString("en-IN", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}{" "}
                    · {m.status.replaceAll("_", " ")}
                  </small>
                </div>
              ))}
              <div ref={end} />
            </div>
            {data.mode.demo && role === "customer" && (
              <div className="suggestions">
                {suggestions.map((s) => (
                  <button key={s} onClick={() => setText(s)}>
                    {s}
                  </button>
                ))}
              </div>
            )}
            <form
              className="composer"
              onSubmit={(e) => {
                e.preventDefault();
                send();
              }}
            >
              {data.mode.demo ? (
                <label className="role-select">
                  <span className="sr-only">Send as</span>
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                  >
                    <option value="customer">Demo customer</option>
                    <option value="seller">Seller</option>
                  </select>
                  <ChevronDown size={13} />
                </label>
              ) : (
                <span>Seller reply</span>
              )}
              <div className="compose-row">
                {data.mode.demo && role === "customer" && (
                  <>
                    <input
                      ref={upload}
                      type="file"
                      hidden
                      accept="image/jpeg,image/png,image/webp"
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) attach(f);
                        e.target.value = "";
                      }}
                    />
                    <button
                      type="button"
                      className="icon-button"
                      aria-label="Attach product photo"
                      disabled={busy}
                      onClick={() => upload.current?.click()}
                    >
                      <Paperclip size={20} />
                    </button>
                  </>
                )}
                <textarea
                  aria-label="Message"
                  placeholder={
                    role === "seller" && !conv.handoff
                      ? "Take over the conversation to send a seller reply"
                      : "Write a message…"
                  }
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  maxLength={4000}
                  rows={2}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      send();
                    }
                  }}
                />
                <button
                  className="send-button"
                  type="submit"
                  aria-label="Send message"
                  disabled={
                    busy || !text.trim() || (role === "seller" && !conv.handoff)
                  }
                >
                  <Send size={19} />
                </button>
              </div>
              <p>
                {busy
                  ? "Processing your message…"
                  : "Enter to send · Shift + Enter for a new line"}
              </p>
            </form>
          </section>
          <aside className="customer-context">
            <div className="eyebrow">CUSTOMER CONTEXT</div>
            <h3>{conv.customer_name}</h3>
            {order && (
              <>
                <div className="context-card">
                  <span className="eyebrow">CURRENT ORDER</span>
                  <h4>{order.id}</h4>
                  <p>{order.product_name}</p>
                  <Badge value={order.status} />
                </div>
                <h4>Related requests</h4>
                {data.cases
                  .filter((c) => c.conversation_id === conv.id)
                  .map((c) => (
                    <div className="context-request" key={c.id}>
                      <strong>{c.kind}</strong>
                      <Badge value={c.status} />
                      {c.status === "pending_customer" && data.mode.demo && (
                        <button
                          className="text-link"
                          onClick={() => {
                            setRole("customer");
                            setText(`CONFIRM ${c.id}`);
                          }}
                        >
                          Prepare confirmation
                        </button>
                      )}
                    </div>
                  ))}
              </>
            )}
            <div className="context-note">
              <ShieldCheck size={20} />
              <p>
                Each action checks the published policy and records the outcome.
              </p>
            </div>
          </aside>
        </>
      ) : (
        <Empty
          title="No conversations yet"
          text="Incoming customer messages will appear here."
        />
      )}
    </div>
  );
}
