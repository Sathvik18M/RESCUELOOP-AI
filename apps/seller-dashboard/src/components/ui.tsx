"use client";
import { useEffect, useRef } from "react";
import {
  X,
  ArrowUpRight,
  CheckCircle2,
  CircleDashed,
  Headphones,
  Wallet,
} from "lucide-react";
import { title } from "@/lib/api";

export function Badge({ value }: { value: string }) {
  const color =
    /completed|delivered|collected|approved|published|ready|succeeded/.test(
      value,
    )
      ? "green"
      : /pending|draft|reserved|queued|needs/.test(value)
        ? "amber"
        : /failed|rejected|declined|cancelled|expired|uncertain/.test(value)
          ? "red"
          : "gray";
  return (
    <span className={`badge ${color}`}>
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
      <CircleDashed size={32} />
      <h3>{heading}</h3>
      <p>{text}</p>
    </div>
  );
}
export function ProductArt({
  kind,
  large = false,
}: {
  kind: string;
  large?: boolean;
}) {
  return (
    <div
      className={`product-art ${kind.includes("HEAD") ? "headphone" : "wallet"} ${large ? "large" : ""}`}
    >
      {kind.includes("HEAD") ? (
        <Headphones size={large ? 88 : 26} strokeWidth={1.25} />
      ) : (
        <Wallet size={large ? 88 : 26} strokeWidth={1.25} />
      )}
      <span />
    </div>
  );
}
export function Modal({
  title: heading,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
    const el = ref.current;
    return () => el?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className="modal"
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <header>
        <h2>{heading}</h2>
        <button
          className="icon-button"
          aria-label="Close dialog"
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
export function Success({ children }: { children: React.ReactNode }) {
  return (
    <div className="notice">
      <CheckCircle2 size={17} />
      {children}
    </div>
  );
}
export function TextLink({
  children,
  onClick,
}: {
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button className="text-link" onClick={onClick}>
      {children}
      <ArrowUpRight size={15} />
    </button>
  );
}
