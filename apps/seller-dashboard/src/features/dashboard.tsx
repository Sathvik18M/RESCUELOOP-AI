"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  MessageCircle,
  ClipboardList,
  ShieldCheck,
  ChartNoAxesCombined,
  Search,
  LogOut,
  KeyRound,
  Menu,
  RefreshCw,
  LoaderCircle,
  AlertCircle,
  CalendarDays,
} from "lucide-react";
import { api, ApiError, DEMO } from "@/lib/api";
import { supabase } from "@/lib/auth";
import { Workspace } from "@/lib/types";
import { Brand, Badge } from "@/components/ui";
import { Login, StoreSetup } from "./seller-auth";
import { ManageRecoveryCodes } from "./seller-recovery";
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
type SellerSession = { userId: string; token: string };

export function Dashboard() {
  const [session, setSession] = useState<SellerSession | null | undefined>(
    undefined,
  );
  const [authError, setAuthError] = useState("");
  useEffect(() => {
    if (DEMO) {
      const token = sessionStorage.getItem("rescueloop-token");
      setSession(token ? { userId: "demo", token } : null);
      return;
    }
    try {
      const { auth } = supabase();
      void auth.initialize().then(({ error }) => {
        if (error) setAuthError(error.message);
      });
      const { data } = auth.onAuthStateChange((_event, current) => {
        setSession(
          current
            ? { userId: current.user.id, token: current.access_token }
            : null,
        );
        if (current) setAuthError("");
      });
      return () => data.subscription.unsubscribe();
    } catch (err) {
      setAuthError(
        err instanceof Error ? err.message : "Could not initialize sign-in.",
      );
      setSession(null);
    }
  }, []);
  async function logout() {
    if (!DEMO) {
      const { error } = await supabase().auth.signOut();
      if (error) throw error;
    }
    sessionStorage.removeItem("rescueloop-token");
    setSession(null);
  }
  if (session === undefined)
    return (
      <div className="loading">
        <LoaderCircle className="spin" />
        Opening your workspace…
      </div>
    );
  if (!session)
    return (
      <Login
        initialError={authError}
        onDemoLogin={(token) => {
          sessionStorage.setItem("rescueloop-token", token);
          setSession({ userId: "demo", token });
        }}
      />
    );
  return (
    <SellerWorkspace
      key={session.userId}
      token={session.token}
      onSignOut={logout}
    />
  );
}

function SellerWorkspace({
  token,
  onSignOut,
}: {
  token: string;
  onSignOut: () => Promise<void>;
}) {
  const section = usePathname().split("/")[1] || "overview";
  const [needsStore, setNeedsStore] = useState(false);
  const [manageCodes, setManageCodes] = useState(false);
  const [data, setData] = useState<Workspace | null>(null),
    [error, setError] = useState(""),
    [search, setSearch] = useState(""),
    [selected, setSelected] = useState<string | null>(null),
    [mobile, setMobile] = useState(false),
    [dates, setDates] = useState({ from: "", to: "" }),
    [toast, setToast] = useState<{ text: string; error: boolean } | null>(null);
  const refresh = useCallback(async () => {
    try {
      const query =
        dates.from && dates.to
          ? "?date_from=" + dates.from + "&date_to=" + dates.to
          : "";
      const next = await api<Workspace>("/workspace" + query, token);
      setData(next);
      setError("");
    } catch (e) {
      if (
        !DEMO &&
        e instanceof ApiError &&
        e.status === 403 &&
        e.message === "No store membership"
      ) {
        setNeedsStore(true);
        setData(null);
        return;
      }
      setError(e instanceof Error ? e.message : "Could not reach the backend");
    }
  }, [token, dates]);
  useEffect(() => {
    if (needsStore) return;
    void refresh();
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, 8000);
    return () => clearInterval(timer);
  }, [refresh, needsStore]);
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
  if (manageCodes)
    return <ManageRecoveryCodes onClose={() => setManageCodes(false)} />;
  if (needsStore)
    return (
      <StoreSetup
        onRecovery={() => setManageCodes(true)}
        onSignOut={onSignOut}
        onCreate={async (name) => {
          await api("/workspace", token, {
            method: "POST",
            body: JSON.stringify({ name }),
          });
          setNeedsStore(false);
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
          <span className="store-avatar">
            {data?.merchant.name.charAt(0).toUpperCase()}
          </span>
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
          {!DEMO && (
            <button className="nav-item" onClick={() => setManageCodes(true)}>
              <KeyRound size={18} /> Recovery codes
            </button>
          )}
          <button
            className="nav-item"
            onClick={() =>
              void onSignOut().catch((err) =>
                setToast({
                  text:
                    err instanceof Error ? err.message : "Could not sign out.",
                  error: true,
                }),
              )
            }
          >
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
              <span className="eyebrow">
                {data?.merchant.name.toUpperCase() || "WORKSPACE"} / CUSTOMER
                SUPPORT
              </span>
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
