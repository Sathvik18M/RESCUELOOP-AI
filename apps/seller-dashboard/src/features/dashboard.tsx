"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  MessageCircle,
  ClipboardList,
  ShieldCheck,
  ChartNoAxesCombined,
  Search,
  LogOut,
  Menu,
  RefreshCw,
  LoaderCircle,
  ArrowUpRight,
  AlertCircle,
  CalendarDays,
  Moon,
  Sun,
} from "lucide-react";
import { api, DEMO } from "@/lib/api";
import { supabase } from "@/lib/auth";
import { Workspace } from "@/lib/types";
import { Brand, Badge } from "@/components/ui";
import { RotatingGlobe } from "@/components/RotatingGlobe";
import { Overview } from "./overview";
import { Requests } from "./requests";
import { Inbox } from "./inbox";
import { Policies } from "./policies";
import { Insights } from "./insights";
import { CaseDetail } from "./case-detail";
const navigation = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "inbox", label: "Inbox", icon: MessageCircle },
  { id: "requests", label: "Requests", icon: ClipboardList },
  { id: "policies", label: "Policies", icon: ShieldCheck },
  { id: "insights", label: "Insights", icon: ChartNoAxesCombined },
];
const descriptions: Record<string, string> = {
  overview: "A clear view of your customer support.",
  inbox: "Every conversation, with the context to help.",
  requests: "Review decisions and follow each request through.",
  policies: "Your rules. Clear boundaries for your AI.",
  insights: "What your customers are telling you.",
};
function Login({ onLogin }: { onLogin: (token: string) => void }) {
  const [theme, setTheme] = useState<"light" | "dark" | null>(null);
  useEffect(() => {
    const preference = window.matchMedia("(prefers-color-scheme: dark)");
    const followSystem = () => setTheme(preference.matches ? "dark" : "light");
    followSystem();
    preference.addEventListener("change", followSystem);
    return () => preference.removeEventListener("change", followSystem);
  }, []);
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [demoToken, setDemoToken] = useState("local-rescueloop-demo"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      let token = demoToken;
      if (!DEMO) {
        const result = await supabase().auth.signInWithPassword({
          email,
          password,
        });
        if (result.error) throw result.error;
        token = result.data.session!.access_token;
      }
      await api("/workspace", token);
      onLogin(token);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }
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
        <form onSubmit={submit}>
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
          <h1>Welcome to your loop.</h1>
          <p>
            {DEMO
              ? "Explore Loop & Co. with saved, synthetic support cases."
              : "Sign in to your store’s support workspace."}
          </p>
          {DEMO ? (
            <>
              <div className="notice">
                Local verification · Synthetic demo data
              </div>
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
                Email address
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  required
                />
              </label>
              <label>
                Password
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                />
              </label>
            </>
          )}
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button className="button primary full" disabled={busy}>
            {busy ? <LoaderCircle size={17} className="spin" /> : null}
            {DEMO ? "Enter seller dashboard" : "Sign in"}
            <ArrowUpRight size={16} />
          </button>
          <p className="helper">
            Customers connect through WhatsApp. This workspace is for the store
            team.
          </p>
        </form>
      </div>
      <aside className="login-visual" aria-label="Care that comes full circle">
        <RotatingGlobe />
        <p className="login-visual-caption">Care that comes full circle.</p>
      </aside>
    </main>
  );
}
export function Dashboard() {
  const section = usePathname().split("/")[1] || "overview";
  const [token, setToken] = useState<string | null>(null),
    [ready, setReady] = useState(false),
    [data, setData] = useState<Workspace | null>(null),
    [error, setError] = useState(""),
    [search, setSearch] = useState(""),
    [selected, setSelected] = useState<string | null>(null),
    [mobile, setMobile] = useState(false),
    [dates, setDates] = useState({ from: "", to: "" }),
    [toast, setToast] = useState<{ text: string; error: boolean } | null>(null);
  useEffect(() => {
    if (DEMO) {
      setToken(sessionStorage.getItem("rescueloop-token"));
      setReady(true);
      return;
    }
    try {
      const client = supabase();
      client.auth.getSession().then(({ data }) => {
        setToken(data.session?.access_token || null);
        setReady(true);
      });
      const { data: listener } = client.auth.onAuthStateChange(
        (_event, session) => setToken(session?.access_token || null),
      );
      return () => listener.subscription.unsubscribe();
    } catch {
      setReady(true);
    }
  }, []);
  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      const query =
        dates.from && dates.to
          ? "?date_from=" + dates.from + "&date_to=" + dates.to
          : "";
      const next = await api<Workspace>("/workspace" + query, token);
      setData(next);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reach the backend");
    }
  }, [token, dates]);
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, 8000);
    return () => clearInterval(timer);
  }, [refresh]);
  useEffect(() => {
    setSearch("");
    setMobile(false);
  }, [section]);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 6500);
    return () => clearTimeout(t);
  }, [toast]);
  async function mutate(path: string, body: unknown = {}, method = "POST") {
    if (!token) return;
    try {
      await api(path, token, { method, body: JSON.stringify(body) });
      await refresh();
      setToast({ text: "Saved. Your workspace is up to date.", error: false });
    } catch (e) {
      setToast({
        text:
          e instanceof Error ? e.message : "The action could not be completed",
        error: true,
      });
      throw e;
    }
  }
  async function logout() {
    if (!DEMO) await supabase().auth.signOut();
    sessionStorage.removeItem("rescueloop-token");
    setToken(null);
    setData(null);
  }
  if (!ready)
    return (
      <div className="loading">
        <LoaderCircle className="spin" />
        Opening your workspace…
      </div>
    );
  if (!token)
    return (
      <Login
        onLogin={(v) => {
          if (DEMO) sessionStorage.setItem("rescueloop-token", v);
          setToken(v);
        }}
      />
    );
  const current = navigation.find((n) => n.id === section);
  const item = data?.cases.find((c) => c.id === selected);
  return (
    <div className="app-shell">
      {mobile && (
        <button
          className="nav-backdrop"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        />
      )}
      <aside className={"sidebar " + (mobile ? "open" : "")}>
        <Link href="/" aria-label="RescueLoop home">
          <Brand />
        </Link>
        <div className="store-switch">
          <span className="store-avatar">L</span>
          <div>
            <strong>{data?.merchant.name || "Your store"}</strong>
            <small>Seller portal</small>
          </div>
          <span className="store-dot" />
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {navigation.map((n) => (
            <Link
              key={n.id}
              className={"nav-item " + (section === n.id ? "active" : "")}
              href={n.id === "overview" ? "/" : "/" + n.id}
              aria-current={section === n.id ? "page" : undefined}
            >
              <n.icon size={19} strokeWidth={1.7} />
              <span>{n.label}</span>
              {n.id === "requests" && !!data?.metrics.flagged && (
                <b>{data.metrics.flagged}</b>
              )}
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="care-card">
            <ShieldCheck size={21} />
            <strong>You're in control.</strong>
            <p>
              Your policies guide every action.
              <br />
              Your decisions handle the rest.
            </p>
          </div>
          <button className="nav-item" onClick={logout}>
            <LogOut size={18} />
            Sign out
          </button>
          <div className="sidebar-version">
            <span className="live-dot" />
            Seller workspace<span>v1.0</span>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumbs">
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              onClick={() => setMobile(true)}
            >
              <Menu size={21} />
            </button>
            <span>Workspace</span>
            <span>/</span>
            <strong>{current?.label || "Not found"}</strong>
          </div>
          <div className="top-actions">
            {["requests", "inbox"].includes(section) && (
              <label className="global-search">
                <Search size={16} />
                <input
                  aria-label="Search current view"
                  placeholder="Search this view…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </label>
            )}
            <span className="top-divider" />
            <span className="avatar">S</span>
            <span className="profile-label">Store team</span>
          </div>
        </header>
        <main className="workspace-content">
          <div className="page-heading">
            <div>
              <span className="eyebrow">LOOP & CO. / CUSTOMER SUPPORT</span>
              <h1>
                {section === "overview"
                  ? "A little care goes a long way."
                  : current?.label || "Page not found"}
              </h1>
              <p>{descriptions[section]}</p>
            </div>
            <div className="heading-actions">
              {data && <Badge value={data.mode.service_status} />}
              <button
                className="icon-button"
                aria-label="Refresh workspace"
                onClick={() => void refresh()}
              >
                <RefreshCw size={17} />
              </button>
            </div>
          </div>
          {data && (
            <div className="view-toolbar">
              <div>
                {data.mode.demo ? (
                  <span className="demo-label">
                    <i />
                    Illustrative demo data · Saved support cases
                  </span>
                ) : (
                  <span className="helper">
                    Current status of cases created in this period
                  </span>
                )}
              </div>
              <div className="date-range">
                <CalendarDays size={15} />
                <input
                  type="date"
                  aria-label="Start date"
                  value={dates.from || data.date_range.from}
                  max={dates.to || data.date_range.to}
                  onChange={(e) =>
                    setDates({
                      from: e.target.value,
                      to: dates.to || data.date_range.to,
                    })
                  }
                />
                <span>–</span>
                <input
                  type="date"
                  aria-label="End date"
                  value={dates.to || data.date_range.to}
                  min={dates.from || data.date_range.from}
                  onChange={(e) =>
                    setDates({
                      from: dates.from || data.date_range.from,
                      to: e.target.value,
                    })
                  }
                />
              </div>
            </div>
          )}
          {error && (
            <div className="error-banner" role="alert">
              <AlertCircle size={18} />
              <span>{error}</span>
              <button onClick={() => void refresh()}>Retry</button>
            </div>
          )}
          {!data ? (
            <div className="loading">
              <LoaderCircle className="spin" />
              Loading store records…
            </div>
          ) : (
            <>
              {section === "overview" && (
                <Overview data={data} onCase={setSelected} />
              )}{" "}
              {section === "inbox" && (
                <Inbox
                  data={data}
                  mutate={mutate}
                  onCase={setSelected}
                  search={search}
                />
              )}{" "}
              {section === "requests" && (
                <Requests data={data} onCase={setSelected} search={search} />
              )}{" "}
              {section === "policies" && (
                <Policies data={data} mutate={mutate} />
              )}{" "}
              {section === "insights" && (
                <Insights data={data} mutate={mutate} onCase={setSelected} />
              )}{" "}
              {!current && <Link href="/">Return to overview</Link>}
            </>
          )}
        </main>
        <footer className="workspace-footer">
          <span>RescueLoop AI · Care, full circle.</span>
          <span>
            {data?.mode.ai === "demo"
              ? "Local verification · Live integrations pending"
              : "Seller portal · WhatsApp support"}
          </span>
        </footer>
      </div>
      {item && data && (
        <CaseDetail
          key={item.id}
          item={item}
          data={data}
          mutate={mutate}
          token={token}
          onClose={() => setSelected(null)}
        />
      )}
      {toast && (
        <div
          className={"toast " + (toast.error ? "error" : "")}
          role={toast.error ? "alert" : "status"}
        >
          {toast.text}
        </div>
      )}
    </div>
  );
}
