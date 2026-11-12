"use client";
import { useState, useEffect, useRef } from "react";
import Image from "next/image";
import { Send, UserRound, ArrowUpRight, MessageCircle } from "lucide-react";
import { Workspace, Conversation, Mutate, Message } from "@/lib/types";
import { Badge, Empty } from "@/components/ui";
import { shortDate, title } from "@/lib/api";
export function Messages({
  messages,
  mutate,
}: {
  messages: Message[];
  mutate?: Mutate;
}) {
  return (
    <div className="messages">
      {messages.map((m) => (
        <article
          key={m.id}
          className={
            "message " + (m.role === "customer" ? "customer" : "outgoing")
          }
        >
          <div className="message-author">
            {m.role === "customer"
              ? "Customer"
              : m.role === "seller"
                ? "Store team"
                : m.role === "system"
                  ? "Store update"
                  : "RescueLoop AI"}
          </div>
          <p>{m.body}</p>
          {m.id === "SHOWCASE-MESSAGE-13-3" && (
            <figure className="message-attachment">
              <Image
                src="/brand/damaged-headphones.svg"
                alt="Illustration showing headphones with a broken headband"
                width={900}
                height={620}
                unoptimized
              />
              <figcaption>Attachment illustration · Broken headband</figcaption>
            </figure>
          )}
          <small>
            {shortDate(m.created_at)} · {title(m.status)}
          </small>
          {m.role !== "customer" &&
            ["uncertain", "failed"].includes(m.status) &&
            !m.provider_id?.trim() && (
              <div className="message-delivery-note" role="note">
                <strong>
                  {m.status === "uncertain"
                    ? "Message delivery is unconfirmed."
                    : "This message could not be sent."}
                </strong>
                <span>
                  No provider tracking ID is recorded, so an automatic delivery
                  check is unavailable.
                </span>
                <span>
                  {m.status === "uncertain"
                    ? "Confirm receipt with the customer before sending again."
                    : "Review the messaging provider’s connection or quota before trying a new message."}
                </span>
              </div>
            )}
          {mutate &&
            m.role !== "customer" &&
            !!m.provider_id?.trim() &&
            ["uncertain", "failed"].includes(m.status) && (
              <button
                className="text-link"
                onClick={() =>
                  void mutate("/messages/" + m.id + "/reconcile", {}).catch(
                    () => {},
                  )
                }
              >
                Check message delivery
              </button>
            )}
        </article>
      ))}
    </div>
  );
}
export function Inbox({
  data,
  mutate,
  onCase,
  search = "",
}: {
  data: Workspace;
  mutate: Mutate;
  onCase: (id: string) => void;
  search?: string;
}) {
  const conversations = [...data.conversations].sort((a, b) => {
    const rank = (c: Conversation) =>
      c.id === "SHOWCASE-CONVERSATION-29"
        ? 0
        : c.id === "SHOWCASE-CONVERSATION-13"
          ? 1
          : c.id.startsWith("SHOWCASE-CONVERSATION-")
            ? 2
            : 3;
    return rank(a) - rank(b);
  });
  const [selected, setSelected] = useState(conversations[0]?.id || "");
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const conv = data.conversations.find((c) => c.id === selected);
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "nearest" });
  }, [selected, conv?.messages.length]);
  const cases = data.cases.filter((c) => c.conversation_id === selected);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.trim() || !conv) return;
    setBusy(true);
    try {
      await mutate("/conversations/" + conv.id + "/reply", {
        text: draft,
        message_id: crypto.randomUUID(),
      });
      setDraft("");
    } catch {
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="inbox-layout">
      <aside className="conversation-list">
        <div className="list-heading">
          <h2>Conversations</h2>
          <span>{data.conversations.length}</span>
        </div>
        {conversations
          .filter((c) =>
            c.customer_name.toLowerCase().includes(search.toLowerCase()),
          )
          .map((c) => (
            <button
              key={c.id}
              className={
                "conversation-option " + (c.id === selected ? "selected" : "")
              }
              onClick={() => {
                setSelected(c.id);
                setDraft("");
              }}
            >
              <span className="avatar">
                {c.customer_name
                  .split(" ")
                  .map((n) => n[0])
                  .slice(0, 2)
                  .join("")}
              </span>
              <span>
                <strong>{c.customer_name}</strong>
                <p>{c.messages.at(-1)?.body || "No messages yet"}</p>
                <small>
                  {c.channel === "demo"
                    ? "Sample conversation"
                    : c.handoff
                      ? "Seller handling"
                      : "WhatsApp"}
                </small>
              </span>
            </button>
          ))}
        <p className="list-footer">
          <MessageCircle size={13} /> Customers message through WhatsApp.
        </p>
      </aside>
      {conv ? (
        <section className="conversation-thread">
          <header>
            <div>
              <h2>{conv.customer_name}</h2>
              <p>
                {conv.channel === "demo"
                  ? "Sample conversation · Prepared support scenario"
                  : conv.handoff
                    ? "Store team is handling this conversation"
                    : data.mode.ai === "demo"
                      ? "Local verification · synthetic conversation"
                      : "AI assistance enabled"}
              </p>
            </div>
            <button
              className={conv.handoff ? "button primary" : "button"}
              onClick={() =>
                void mutate(
                  "/conversations/" + conv.id + "/handoff",
                  { enabled: !conv.handoff },
                  "PATCH",
                ).catch(() => {})
              }
            >
              <UserRound size={15} />
              {conv.handoff ? "Resume AI" : "Take over"}
            </button>
          </header>
          <div className="thread-scroll">
            <Messages messages={conv.messages} mutate={mutate} />
            <div ref={bottom} />
          </div>
          <div className="related-cases">
            {cases.map((c) => (
              <button key={c.id} onClick={() => onCase(c.id)}>
                {title(c.kind)} <Badge value={c.primary_status} />
                <ArrowUpRight size={14} />
              </button>
            ))}
          </div>
          <form className="reply-composer" onSubmit={submit}>
            <label htmlFor="seller-reply">
              {conv.handoff
                ? "Reply as store team"
                : "Take over to reply personally"}
            </label>
            <div>
              <textarea
                id="seller-reply"
                aria-label="Seller reply"
                value={draft}
                disabled={!conv.handoff || busy}
                onChange={(e) => setDraft(e.target.value)}
                placeholder={
                  conv.handoff
                    ? "Write a message to the customer…"
                    : "AI assistance is managing this conversation."
                }
              />
              <button
                className="button primary"
                aria-label="Send seller reply"
                disabled={!conv.handoff || !draft.trim() || busy}
              >
                <Send size={18} />
              </button>
            </div>
          </form>
        </section>
      ) : (
        <Empty
          title="Select a conversation"
          text="Customer messages will appear here."
        />
      )}
    </div>
  );
}
