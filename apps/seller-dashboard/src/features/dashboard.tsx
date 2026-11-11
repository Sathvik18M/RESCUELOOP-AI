"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  MessageCircle,
  ShoppingBag,
  Package,
  ShieldCheck,
  Sparkles,
  MapPin,
  RotateCcw,
  ImageIcon,
  Star,
  ChartNoAxesCombined,
  ListChecks,
  Settings as SettingsIcon,
  Search,
  Bell,
  ChevronDown,
  ArrowUpRight,
  LogOut,
  Menu,
  X,
  FlaskConical,
  LoaderCircle,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
} from "lucide-react";
import { api, DEMO } from "@/lib/api";
import { supabase } from "@/lib/auth";
import { Workspace, CaseRecord } from "@/lib/types";
import { Overview } from "./overview";
import {
  Approvals,
  DecisionModal,
  Orders,
  Products,
  Pickups,
} from "./commerce";
import { Inbox } from "./inbox";
import { Policies } from "./policies";
import {
  EvidenceGallery,
  Feedback,
  Insights,
  Activity,
  Settings,
} from "./reports";
import { Modal } from "@/components/ui";

const navigation = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "inbox", label: "WhatsApp inbox", icon: MessageCircle },
  { id: "orders", label: "Orders", icon: ShoppingBag },
  { id: "products", label: "Products & inventory", icon: Package },
  { id: "approvals", label: "Requests & approvals", icon: Sparkles },
  { id: "policies", label: "Policy studio", icon: ShieldCheck },
  { id: "pickup", label: "Store pickup", icon: MapPin },
  { id: "returns", label: "Returns & refunds", icon: RotateCcw },
  { id: "evidence", label: "Evidence gallery", icon: ImageIcon },
  { id: "feedback", label: "Customer feedback", icon: Star },
  { id: "insights", label: "Insights & reports", icon: ChartNoAxesCombined },
  { id: "activity", label: "Action log", icon: ListChecks },
];

function Brand() {
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

function Login({ onLogin }: { onLogin: (token: string) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [demoToken, setDemoToken] = useState("local-rescueloop-demo");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      let token = demoToken;
      if (!DEMO) {
        const { data, error } = await supabase().auth.signInWithPassword({
          email,
          password,
        });
        if (error) throw error;
        token = data.session!.access_token;
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
    <main className="login-page">
      <div className="login-story">
        <Brand />
        <div>
          <span className="eyebrow">CUSTOMER CARE, FULL CIRCLE</span>
          <h1>
            Good experiences
            <br />
            keep coming
            <br />
            <em>back around.</em>
          </h1>
          <p>
            One place for your conversations, decisions,
            <br />
            and everything that happens next.
          </p>
        </div>
        <span className="login-caption">
          Thoughtful support. Connected commerce.
        </span>
      </div>
      <div className="login-form">
        <form onSubmit={submit}>
          <span className="eyebrow">SELLER WORKSPACE</span>
          <h2>Welcome to your loop.</h2>
          <p>
            {DEMO
              ? "Explore the demo store and see every customer request through."
              : "Sign in to manage your store and customer conversations."}
          </p>
          {DEMO ? (
            <>
              <div className="demo-login">
                <FlaskConical size={19} />
                <span>Local demo · Synthetic customer data</span>
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
                  required
                  autoComplete="email"
                />
              </label>
              <label>
                Password
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
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
            {busy ? <LoaderCircle className="spin" size={18} /> : null}
            {DEMO ? "Enter demo workspace" : "Sign in"}
            <ArrowUpRight size={17} />
          </button>
          <p className="login-fine">
            {DEMO
              ? "Run the backend and seed the database before entering. Live services can be connected in your environment configuration."
              : "Access is limited to authorized members of your store."}
          </p>
        </form>
      </div>
    </main>
  );
}

export function Dashboard() {
  const pathname = usePathname();
  const router = useRouter();
  const section = pathname.split("/")[1] || "overview";
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [data, setData] = useState<Workspace | null>(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [review, setReview] = useState<CaseRecord | null>(null);
  const [mobile, setMobile] = useState(false);
  const [studio, setStudio] = useState(false);
  const [toast, setToast] = useState<{ text: string; error: boolean } | null>(
    null,
  );
  const notify = useCallback(
    (text: string, error = false) => setToast({ text, error }),
    [],
  );
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
      const { data: subscription } = client.auth.onAuthStateChange(
        (_event, session) => setToken(session?.access_token || null),
      );
      return () => subscription.subscription.unsubscribe();
    } catch {
      setReady(true);
    }
  }, []);
  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      const next = await api<Workspace>("/workspace", token);
      setData(next);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reach the backend");
    }
  }, [token]);
  useEffect(() => {
    refresh();
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") refresh();
    }, 8000);
    return () => clearInterval(timer);
  }, [refresh]);
  useEffect(() => {
    setSearch("");
    setMobile(false);
  }, [section]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 5500);
    return () => clearTimeout(timer);
  }, [toast]);
  async function mutate(path: string, body: unknown, method = "POST") {
    if (!token) return;
    try {
      await api(path, token, { method, body: JSON.stringify(body) });
      await refresh();
      notify("Saved. Your workspace is up to date.");
    } catch (e) {
      notify(
        e instanceof Error ? e.message : "The action could not be completed",
        true,
      );
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
        <p>Opening your workspace…</p>
      </div>
    );
  if (!token)
    return (
      <Login
        onLogin={(value) => {
          if (DEMO) sessionStorage.setItem("rescueloop-token", value);
          setToken(value);
        }}
      />
    );
  const current = navigation.find((n) => n.id === section);
  const heading =
    section === "settings"
      ? "Store settings"
      : current?.label || "Page not found";
  return (
    <div className="app-shell">
      {mobile && (
        <button
          aria-label="Close navigation"
          className="nav-backdrop"
          onClick={() => setMobile(false)}
        />
      )}
      <aside className={`sidebar ${mobile ? "open" : ""}`}>
        <Link href="/" aria-label="RescueLoop home">
          <Brand />
        </Link>
        <div className="store-switch">
          <span className="store-avatar">L</span>
          <div>
            <strong>{data?.merchant.name || "Your store"}</strong>
            <small>Seller workspace</small>
          </div>
          <ChevronDown size={15} />
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {navigation.map((n, i) => (
            <div key={n.id}>
              {i === 8 && (
                <div className="nav-label secondary">INTELLIGENCE</div>
              )}
              <Link
                href={n.id === "overview" ? "/" : `/${n.id}`}
                className={`nav-item ${section === n.id ? "active" : ""}`}
                aria-current={section === n.id ? "page" : undefined}
              >
                <n.icon size={18} strokeWidth={1.7} />
                <span>{n.label}</span>
                {n.id === "approvals" && !!data?.metrics.pending && (
                  <b>{data.metrics.pending}</b>
                )}
              </Link>
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="care-card">
            <ShieldCheck size={20} />
            <strong>You're in control.</strong>
            <p>
              Your policies. Your approvals.
              <br />
              AI that follows your lead.
            </p>
          </div>
          <Link
            href="/settings"
            className={`nav-item ${section === "settings" ? "active" : ""}`}
          >
            <SettingsIcon size={18} />
            Settings
          </Link>
          <button className="nav-item" onClick={logout}>
            <LogOut size={18} />
            Sign out
          </button>
          <div className="sidebar-version">
            <span className="live-dot" />
            {data?.mode.demo ? "Demo workspace" : "Store workspace"}
            <span>v0.1</span>
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
            <strong>{heading}</strong>
          </div>
          <div className="top-actions">
            <label className="global-search">
              <Search size={16} />
              <input
                aria-label="Search current view"
                placeholder="Search this view…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </label>
            <button
              className="notification-button"
              aria-label="View pending approvals"
              onClick={() => router.push("/approvals")}
            >
              <Bell size={19} />
              {!!data?.metrics.pending && <i />}
            </button>
            <span className="top-divider" />
            <button
              className="profile"
              aria-label="Open store settings"
              onClick={() => router.push("/settings")}
            >
              <span className="avatar">S</span>
              <span>Store owner</span>
              <ChevronDown size={14} />
            </button>
          </div>
        </header>
        <main
          className={`workspace-content ${section === "inbox" ? "inbox-page" : ""}`}
        >
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                {section === "overview"
                  ? "A GOOD DAY TO MAKE SOMEONE'S DAY"
                  : "LOOP & CO. / SELLER WORKSPACE"}
              </div>
              <h1>
                {section === "overview" ? "Your store, in the loop." : heading}
              </h1>
              <p>
                {section === "overview"
                  ? "Here's what's happening across your customer experience."
                  : section === "inbox"
                    ? "One conversation, from the first question to the final follow-up."
                    : "Everything you need, with a clear record of what happens next."}
              </p>
            </div>
            <div className="heading-actions">
              <button
                className="icon-button"
                aria-label="Refresh workspace"
                onClick={refresh}
              >
                <RefreshCw size={17} />
              </button>
              {data?.mode.demo && (
                <button className="button" onClick={() => setStudio(true)}>
                  <FlaskConical size={16} />
                  Demo studio
                </button>
              )}
              <span className="date-chip">
                {new Date().toLocaleDateString("en-IN", {
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                })}
              </span>
            </div>
          </div>
          {error && (
            <div className="error-banner" role="alert">
              <AlertCircle size={18} />
              <span>{error}. Check that the API is running.</span>
              <button onClick={refresh}>Retry</button>
            </div>
          )}
          {!data ? (
            <div className="loading">
              <LoaderCircle className="spin" />
              <p>Loading store records…</p>
            </div>
          ) : (
            <>
              {section === "overview" && (
                <Overview data={data} onReview={setReview} />
              )}
              {section === "inbox" && (
                <Inbox
                  data={data}
                  token={token}
                  mutate={mutate}
                  refresh={refresh}
                  notify={notify}
                  search={search}
                />
              )}
              {section === "orders" && <Orders data={data} search={search} />}
              {section === "products" && (
                <Products data={data} search={search} mutate={mutate} />
              )}
              {section === "approvals" && (
                <Approvals data={data} onReview={setReview} search={search} />
              )}
              {section === "returns" && (
                <Approvals
                  data={data}
                  onReview={setReview}
                  search={search}
                  refunds
                />
              )}
              {section === "policies" && (
                <Policies
                  key={data.policies[0]?.version}
                  data={data}
                  token={token}
                  mutate={mutate}
                  notify={notify}
                />
              )}
              {section === "pickup" && <Pickups data={data} mutate={mutate} />}
              {section === "evidence" && (
                <EvidenceGallery data={data} token={token} />
              )}
              {section === "feedback" && (
                <Feedback data={data} search={search} />
              )}
              {section === "insights" && (
                <Insights data={data} mutate={mutate} />
              )}
              {section === "activity" && (
                <Activity data={data} search={search} />
              )}
              {section === "settings" && (
                <Settings data={data} mutate={mutate} />
              )}
              {!current && section !== "settings" && (
                <p>
                  This workspace page doesn’t exist.{" "}
                  <Link href="/">Return to overview.</Link>
                </p>
              )}
            </>
          )}
        </main>
        <footer className="workspace-footer">
          <span>RescueLoop AI · Care that comes full circle.</span>
          <span>
            <ShieldCheck size={13} />
            Policy-controlled actions
          </span>
        </footer>
      </div>
      {toast && (
        <div
          role={toast.error ? "alert" : "status"}
          className={`toast ${toast.error ? "toast-error" : ""}`}
        >
          {toast.error ? <AlertCircle size={19} /> : <CheckCircle2 size={19} />}
          <span>{toast.text}</span>
          <button
            aria-label="Dismiss notification"
            onClick={() => setToast(null)}
          >
            <X size={16} />
          </button>
        </div>
      )}
      {review && data && (
        <DecisionModal
          item={data.cases.find((c) => c.id === review.id) || review}
          data={data}
          mutate={mutate}
          onClose={() => setReview(null)}
        />
      )}
      {studio && (
        <Modal title="Demo studio" onClose={() => setStudio(false)}>
          <div className="modal-body">
            <p>
              Use the inbox as the demo customer, then return to approvals as
              the seller. Every completed action updates PostgreSQL.
            </p>
            <div className="demo-scenarios">
              <button
                onClick={() => {
                  setStudio(false);
                  router.push("/approvals");
                }}
              >
                <span>01</span>
                <div>
                  <strong>Personalize a gift</strong>
                  <p>
                    Review the wallet engraving quote, then confirm it in the
                    inbox.
                  </p>
                </div>
                <ArrowUpRight size={18} />
              </button>
              <button
                onClick={() => {
                  setStudio(false);
                  router.push("/inbox");
                }}
              >
                <span>02</span>
                <div>
                  <strong>Reserve store pickup</strong>
                  <p>
                    Ask for a pickup slot, approve it, and confirm as the
                    customer.
                  </p>
                </div>
                <ArrowUpRight size={18} />
              </button>
              <button
                onClick={() => {
                  setStudio(false);
                  router.push("/inbox");
                }}
              >
                <span>03</span>
                <div>
                  <strong>Recover a failed delivery</strong>
                  <p>
                    Provide a redelivery address and confirm the courier
                    request.
                  </p>
                </div>
                <ArrowUpRight size={18} />
              </button>
              <button
                onClick={async () => {
                  try {
                    await mutate("/demo/scenarios/delivered", {});
                    setStudio(false);
                    router.push("/inbox");
                  } catch {}
                }}
              >
                <span>04</span>
                <div>
                  <strong>Photo complaint & refund</strong>
                  <p>
                    Mark ORD1042 delivered, then attach a photo and request a
                    refund.
                  </p>
                </div>
                <ArrowUpRight size={18} />
              </button>
            </div>
            <p className="helper">
              Demo AI uses predictable scenarios. Payments and courier actions
              are simulated. Connect OpenAI to enable model reasoning and image
              analysis.
            </p>
          </div>
        </Modal>
      )}
    </div>
  );
}
