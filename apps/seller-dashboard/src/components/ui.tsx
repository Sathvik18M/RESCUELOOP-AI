"use client";
import { useEffect, useRef } from "react";
import { X, CircleDashed } from "lucide-react";
import { title } from "@/lib/api";
export function Badge({ value }: { value: string }) {
  const color =
    /resolved|completed|delivered|collected|published|succeeded|available/.test(
      value,
    ) && !/unavailable/.test(value)
      ? "green"
      : /flagged|failed|uncertain|unavailable/.test(value)
        ? "red"
        : /ongoing|pending|waiting|draft|reserved|verification|delayed/.test(
              value,
            )
          ? "amber"
          : "gray";
  return (
    <span className={"badge " + color}>
      <i />
      {title(value)}
    </span>
  );
}
export function Empty({
  title: heading,
  text,
}: {
  title: string;
  text: string;
}) {
  return (
    <div className="empty">
      <CircleDashed size={30} />
      <h3>{heading}</h3>
      <p>{text}</p>
    </div>
  );
}
export function Modal({
  title: heading,
  onClose,
  children,
  drawer = false,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  drawer?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const el = ref.current;
    el?.showModal();
    return () => el?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className={drawer ? "case-drawer" : "modal"}
      aria-label={heading}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <header className="dialog-heading">
        <h2>{heading}</h2>
        <button
          className="icon-button"
          aria-label="Close case"
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </header>
      {children}
    </dialog>
  );
}
export function SectionTitle({
  title: heading,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="section-title">
      <div>
        <h2>{heading}</h2>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
export function Brand() {
  return (
    <div className="brand">
      <span className="brand-symbol">
        <i />
        <i />
      </span>
      <span>
        rescueloop<span className="brand-ai">AI</span>
      </span>
    </div>
  );
}
export const caseLabel = (id: string) =>
  id.startsWith("CASE")
    ? id.replace("CASE", "#")
    : id.startsWith("HIST")
      ? "#" + id
      : "#" + id.slice(0, 6).toUpperCase();
