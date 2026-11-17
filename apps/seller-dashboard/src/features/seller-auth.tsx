"use client";
import { useState, type FormEvent } from "react";
import { ArrowUpRight, LoaderCircle } from "lucide-react";
import { api, DEMO } from "@/lib/api";
import { passwordLoginId, supabase } from "@/lib/auth";
import { AuthForm } from "./auth-form";
import { SavedRecoveryCodes, ResetPassword } from "./seller-recovery";

export function Login({
  onDemoLogin,
  initialError,
}: {
  onDemoLogin: (token: string) => void;
  initialError: string;
}) {
  const [signup, setSignup] = useState(false);
  const [codes, setCodes] = useState<string[]>([]);
  const [recover, setRecover] = useState(false);
  const [notice, setNotice] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [demoToken, setDemoToken] = useState("local-rescueloop-demo");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const errorMessage = error ?? initialError;

  async function submit(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (DEMO) {
        await api("/workspace", demoToken);
        onDemoLogin(demoToken);
        return;
      }
      const identifier = username.trim();
      if (signup) {
        const account = await api<{
          username: string;
          recovery_codes: string[];
        }>("/auth/signup", null, {
          method: "POST",
          body: JSON.stringify({ username: identifier, password }),
        });
        setUsername(account.username);
        setSignup(false);
        setCodes(account.recovery_codes);
        return;
      }
      const { error } = await supabase().auth.signInWithPassword({
        email: passwordLoginId(identifier),
        password,
      });
      if (error) {
        if (error.code === "invalid_credentials")
          throw new Error("Incorrect username or password.");
        throw error;
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not complete your request. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (codes.length)
    return (
      <SavedRecoveryCodes
        codes={codes}
        onContinue={() => {
          setCodes([]);
          void submit();
        }}
      />
    );
  if (recover)
    return (
      <ResetPassword
        onClose={(changed) => {
          setRecover(false);
          setNotice(
            changed ? "Password reset. Sign in with your new password." : "",
          );
        }}
      />
    );
  return (
    <AuthForm
      title={signup ? "Create your seller account" : "Welcome to your loop."}
      description={
        DEMO
          ? "Explore Loop & Co. with saved, synthetic support cases."
          : signup
            ? "Sign up to open a workspace for your store."
            : "Sign in to your store’s support workspace."
      }
      onSubmit={submit}
    >
      {DEMO ? (
        <>
          <div className="notice">Local verification · Synthetic demo data</div>
          <label>
            Demo access token
            <input
              type="password"
              value={demoToken}
              onChange={(e) => setDemoToken(e.target.value)}
              required
            />
          </label>
        </>
      ) : (
        <>
          <label>
            Username
            <input
              type="text"
              name="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              pattern={signup ? "[A-Za-z0-9][A-Za-z0-9_]{2,31}" : undefined}
              maxLength={signup ? 32 : undefined}
              aria-describedby="username-hint"
              required
            />
          </label>
          <p className="auth-hint" id="username-hint">
            {signup
              ? "Use 3–32 letters, numbers or underscores. Start with a letter or number."
              : "Existing sellers can also sign in with their original email address."}
          </p>
          <label>
            Password
            <input
              type="password"
              name="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={signup ? "new-password" : "current-password"}
              minLength={signup ? 8 : undefined}
              placeholder={signup ? "At least 8 characters" : undefined}
              required
            />
          </label>
        </>
      )}
      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}
      {errorMessage && (
        <p className="form-error" role="alert">
          {errorMessage}
        </p>
      )}
      <button className="button primary full" disabled={busy}>
        {busy && <LoaderCircle size={17} className="spin" />}
        {DEMO
          ? "Enter seller dashboard"
          : signup
            ? "Create account"
            : "Sign in"}
        <ArrowUpRight size={16} />
      </button>
      {!DEMO && !signup && (
        <p className="auth-switch">
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              setPassword("");
              setError("");
              setRecover(true);
            }}
          >
            Forgot password?
          </button>
        </p>
      )}
      {!DEMO && (
        <p className="auth-switch">
          {signup ? "Already have an account? " : "New to RescueLoop? "}
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              setSignup(!signup);
              setNotice("");
              setError("");
              setPassword("");
            }}
          >
            {signup ? "Sign in" : "Sign up"}
          </button>
        </p>
      )}
      <p className="helper">
        Customers connect through WhatsApp. This workspace is for the store
        team.
      </p>
    </AuthForm>
  );
}

export function StoreSetup({
  onCreate,
  onSignOut,
  onRecovery,
}: {
  onCreate: (name: string) => Promise<void>;
  onSignOut: () => Promise<void>;
  onRecovery: () => void;
}) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Please try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <AuthForm
      title="Name your store"
      description="This name appears in your seller workspace."
      onSubmit={(event) => {
        event.preventDefault();
        void run(() => onCreate(name.trim()));
      }}
    >
      <label>
        Store name
        <input
          autoComplete="organization"
          required
          maxLength={120}
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </label>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button className="button primary full" disabled={busy || !name.trim()}>
        Create workspace <ArrowUpRight size={16} />
      </button>
      <p className="auth-switch">
        <button type="button" disabled={busy} onClick={onRecovery}>
          Recovery codes
        </button>
      </p>
      <p className="auth-switch">
        <button
          type="button"
          disabled={busy}
          onClick={() => void run(onSignOut)}
        >
          Sign out
        </button>
      </p>
    </AuthForm>
  );
}
