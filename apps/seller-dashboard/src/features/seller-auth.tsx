"use client";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import Image from "next/image";
import { ArrowUpRight, LoaderCircle, Moon, Sun } from "lucide-react";
import { RotatingGlobe } from "@/components/RotatingGlobe";
import { api, DEMO } from "@/lib/api";
import { passwordLoginId, supabase } from "@/lib/auth";

function AuthForm({
  title,
  description,
  onSubmit,
  children,
}: {
  title: string;
  description: string;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  children: ReactNode;
}) {
  const [theme, setTheme] = useState<"light" | "dark" | null>(null);
  useEffect(() => {
    const preference = window.matchMedia("(prefers-color-scheme: dark)");
    const followSystem = () => setTheme(preference.matches ? "dark" : "light");
    followSystem();
    preference.addEventListener("change", followSystem);
    return () => preference.removeEventListener("change", followSystem);
  }, []);
  return (
    <main className="login-page" data-theme={theme ?? undefined}>
      <div className="login-form">
        <button
          className="login-theme-toggle"
          type="button"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          aria-label={theme === "dark" ? "Use light theme" : "Use dark theme"}
          title={theme === "dark" ? "Use light theme" : "Use dark theme"}
        >
          {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
        </button>
        <form onSubmit={onSubmit}>
          <Image
            className="login-logo"
            src="/brand/rescueloop-logo.png"
            alt="RescueLoop AI — customer care, full circle"
            width={1254}
            height={1254}
            sizes="(max-width: 720px) 144px, (max-height: 760px) 152px, 180px"
            preload
          />
          <span className="eyebrow">SELLER PORTAL</span>
          <h1>{title}</h1>
          <p>{description}</p>
          {children}
        </form>
      </div>
      <aside className="login-visual" aria-label="Care that comes full circle">
        <RotatingGlobe />
        <p className="login-visual-caption">Care that comes full circle.</p>
      </aside>
    </main>
  );
}

export function Login({
  onDemoLogin,
  initialError,
}: {
  onDemoLogin: (token: string) => void;
  initialError: string;
}) {
  const [signup, setSignup] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [demoToken, setDemoToken] = useState("local-rescueloop-demo");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const errorMessage = error ?? initialError;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (DEMO) {
        await api("/workspace", demoToken);
        onDemoLogin(demoToken);
        return;
      }
      let identifier = username.trim();
      if (signup) {
        const account = await api<{ username: string }>("/auth/signup", null, {
          method: "POST",
          body: JSON.stringify({ username: identifier, password }),
        });
        identifier = account.username;
        setUsername(identifier);
        setSignup(false);
      }
      const { error } = await supabase().auth.signInWithPassword({
        email: passwordLoginId(identifier),
        password,
      });
      if (error) {
        if (signup)
          throw new Error(
            "Your account was created. Sign in to open your store.",
          );
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
      {!DEMO && (
        <p className="auth-switch">
          {signup ? "Already have an account? " : "New to RescueLoop? "}
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              setSignup(!signup);
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
}: {
  onCreate: (name: string) => Promise<void>;
  onSignOut: () => Promise<void>;
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
