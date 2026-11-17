"use client";

import { useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import { supabase } from "@/lib/auth";
import { AuthForm } from "./auth-form";

export function SavedRecoveryCodes({
  codes,
  onContinue,
}: {
  codes: string[];
  onContinue: () => void;
}) {
  function download() {
    const file = new Blob(
      [
        "RescueLoop recovery codes\n\n" +
          codes.join("\n") +
          "\n\nEach code can reset your password once. Keep these codes private.\n",
      ],
      { type: "text/plain" },
    );
    const url = URL.createObjectURL(file);
    const link = document.createElement("a");
    link.href = url;
    link.download = "rescueloop-recovery-codes.txt";
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <AuthForm
      title="Save your recovery codes"
      description="Save these codes in your password manager or download a copy. Anyone with one can reset your password. Each works once."
      onSubmit={(e) => {
        e.preventDefault();
        onContinue();
      }}
    >
      <ul className="recovery-codes" aria-label="Your recovery codes">
        {codes.map((code) => (
          <li key={code}>
            <code>{code}</code>
          </li>
        ))}
      </ul>
      <button
        className="button secondary full"
        type="button"
        onClick={download}
      >
        Download codes
      </button>
      <button className="button primary full">I’ve saved my codes</button>
    </AuthForm>
  );
}

export function ManageRecoveryCodes({ onClose }: { onClose: () => void }) {
  const [password, setPassword] = useState("");
  const [codes, setCodes] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const auth = supabase().auth;
      const {
        data: { user },
      } = await auth.getUser();
      if (!user?.email)
        throw new Error("Sign in again to generate recovery codes.");
      const { data, error: signInError } = await auth.signInWithPassword({
        email: user.email,
        password,
      });
      if (signInError || !data.session)
        throw new Error(
          signInError?.code === "invalid_credentials"
            ? "Incorrect password."
            : "Could not confirm your password. Please try again.",
        );
      const result = await api<{ recovery_codes: string[] }>(
        "/auth/recovery-codes",
        data.session.access_token,
        { method: "POST" },
      );
      setPassword("");
      setCodes(result.recovery_codes);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not generate recovery codes.",
      );
    } finally {
      setBusy(false);
    }
  }
  if (codes.length)
    return <SavedRecoveryCodes codes={codes} onContinue={onClose} />;
  return (
    <AuthForm
      title="Recovery codes"
      description="Confirm your password to get three one-time codes. Generating a new set replaces all your previous codes."
      onSubmit={generate}
    >
      <label>
        Current password
        <input
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </label>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button className="button primary full" disabled={busy}>
        Generate recovery codes
      </button>
      <p className="auth-switch">
        <button type="button" disabled={busy} onClick={onClose}>
          Back to workspace
        </button>
      </p>
    </AuthForm>
  );
}

export function ResetPassword({
  onClose,
}: {
  onClose: (changed: boolean) => void;
}) {
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function reset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password !== confirm) {
      setError("Your passwords don’t match.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api<void>("/auth/reset-password", null, {
        method: "POST",
        body: JSON.stringify({ recovery_code: code, new_password: password }),
      });
      onClose(true);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not reset your password.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <AuthForm
      title="Reset your password"
      description="Enter one of your saved RescueLoop recovery codes and choose a new password."
      onSubmit={reset}
    >
      <label>
        Recovery code
        <input
          type="text"
          autoComplete="off"
          spellCheck={false}
          autoCapitalize="characters"
          maxLength={80}
          value={code}
          onChange={(e) => setCode(e.target.value)}
          required
        />
      </label>
      <label>
        New password
        <input
          type="password"
          autoComplete="new-password"
          minLength={8}
          placeholder="At least 8 characters"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </label>
      <label>
        Confirm new password
        <input
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
        />
      </label>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button className="button primary full" disabled={busy}>
        Reset password
      </button>
      <p className="auth-switch">
        <button type="button" disabled={busy} onClick={() => onClose(false)}>
          Back to sign in
        </button>
      </p>
    </AuthForm>
  );
}
