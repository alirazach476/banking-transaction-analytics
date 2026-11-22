import { LogoMark } from "../ui/Logo.jsx";
import React, { Suspense, lazy, useEffect, useRef, useState } from "react";
import { Link, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { Activity, Bell, ChevronsLeft, ChevronsRight, CreditCard, Globe2, KeyRound, Landmark, LayoutDashboard, Menu, Moon, Search, Settings as Cog, ShieldAlert, Scale, Store, Sun, Table2, Users, Zap } from "lucide-react";
import { useApi, useTheme } from "../lib/context.jsx";
import { apiKey } from "../lib/api.js";
import { RangeControl, Skeleton } from "../ui/kit.jsx";

const Overview = lazy(() => import("../pages/Overview.jsx"));
const Payments = lazy(() => import("../pages/Payments.jsx"));
const Fraud = lazy(() => import("../pages/Fraud.jsx"));
const Customers = lazy(() => import("../pages/Customers.jsx"));
const CustomerDetail = lazy(() => import("../pages/CustomerDetail.jsx"));
const Merchants = lazy(() => import("../pages/Merchants.jsx"));
const Branches = lazy(() => import("../pages/Branches.jsx"));
const Explorer = lazy(() => import("../pages/Explorer.jsx"));
const GlobalIntel = lazy(() => import("../pages/GlobalIntel.jsx"));
const Benchmarks = lazy(() => import("../pages/Benchmarks.jsx"));
const Engineering = lazy(() => import("../pages/Engineering.jsx"));
const SettingsPage = lazy(() => import("../pages/Settings.jsx"));

export const NAV = [
  { group: "Analytics" },
  { to: "/overview", label: "Executive Overview", icon: LayoutDashboard, range: true },
  { to: "/payments", label: "Payment Intelligence", icon: CreditCard, range: true },
  { to: "/fraud", label: "Fraud & Anomaly Intelligence", icon: ShieldAlert, range: true },
  { to: "/customers", label: "Customer Analytics", icon: Users, range: true },
  { to: "/merchants", label: "Merchant Analytics", icon: Store, range: true },
  { to: "/branches", label: "Branch & Regional Analytics", icon: Landmark, range: true },
  { group: "Data" },
  { to: "/explorer", label: "Transaction Explorer", icon: Table2, range: true },
  { to: "/global", label: "Global Financial Intelligence", icon: Globe2, range: false },
  { to: "/benchmarks", label: "Real vs Synthetic", icon: Scale, range: false },
  { to: "/engineering", label: "Data Engineering & Monitoring", icon: Activity, range: false },
  { group: "System" },
  { to: "/settings", label: "Settings", icon: Cog, range: false },
];
const FLAT = NAV.filter((n) => n.to);

function useClickAway(ref, fn) {
  useEffect(() => {
    const h = (e) => ref.current && !ref.current.contains(e.target) && fn();
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [ref, fn]);
}

function GlobalSearch() {
  const [v, setV] = useState("");
  const [open, setOpen] = useState(false);
  const [dv, setDv] = useState("");
  const ref = useRef(null);
  const nav = useNavigate();
  useClickAway(ref, () => setOpen(false));
  useEffect(() => { const t = setTimeout(() => setDv(v.trim()), 250); return () => clearTimeout(t); }, [v]);
  const { data } = useApi("/v1/search", { q: dv }, { enabled: dv.length >= 2 });
  const go = (to) => { setOpen(false); setV(""); nav(to); };
  const groups = data ? [["Customers", data.customers, (r) => "/customers/" + r.id], ["Merchants", data.merchants, (r) => "/merchants/" + r.id], ["Branches", data.branches, (r) => "/branches/" + r.id],
    ["Transactions", data.transactions, (r) => "/explorer?tab=transactions&q=" + r.id]] : [];
  return (
    <div className="search" ref={ref}>
      <Search size={16} />
      <input aria-label="Global search" placeholder="Search customers, merchants, branches, transactions…" value={v} onChange={(e) => { setV(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)} />
      {open && dv.length >= 2 && (
        <div className="menu" role="listbox">
          {groups.every(([, rows]) => !rows.length) && <div className="state" style={{ minHeight: 60 }}>No matches</div>}
          {groups.map(([name, rows, link]) => rows.length > 0 && (
            <div key={name}><h4>{name}</h4>{rows.map((r) => <button key={r.id} className="row" onClick={() => go(link(r))}><span>{r.label || r.id}</span><small>{r.id} · {r.detail}</small></button>)}</div>
          ))}
        </div>
      )}
    </div>
  );
}

function Notifications() {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useClickAway(ref, () => setOpen(false));
  const { data } = useApi("/v1/notifications", {}, { refetchInterval: 120_000 });
  const items = data?.items || [];
  return (
    <div style={{ position: "relative" }} ref={ref}>
      <button className="icon-btn" aria-label="Notifications" onClick={() => setOpen(!open)}><Bell size={17} />{items.length > 0 && <span className="dot">{items.length}</span>}</button>
      {open && (
        <div className="menu" role="dialog" aria-label="Notification centre">
          <h4>Notifications (derived from live records)</h4>
          {items.length === 0 && <div className="state" style={{ minHeight: 60 }}>Nothing needs attention</div>}
          {items.map((n, i) => <Link key={i} to={n.to} onClick={() => setOpen(false)}><span>{n.title}</span><span className={"badge " + n.level}>{n.level}</span></Link>)}
        </div>
      )}
    </div>
  );
}

function Profile() {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useClickAway(ref, () => setOpen(false));
  const { data } = useApi("/v1/meta");
  const keyed = !!apiKey();
  return (
    <div style={{ position: "relative" }} ref={ref}>
      <button className="icon-btn" aria-label="Profile" onClick={() => setOpen(!open)}><KeyRound size={17} /></button>
      {open && (
        <div className="menu" role="dialog" aria-label="Session">
          <h4>Session</h4>
          <div style={{ padding: "4px 8px 10px" }}>
            <div><b>{keyed ? "API key session" : "Local development"}</b></div>
            <small style={{ color: "var(--muted)" }}>{keyed ? "Requests are sent with your X-API-Key." : "The API has no authentication configured (" + (data?.auth || "…") + "). Set API_KEY and open the app with ?key=… to require one."}</small>
          </div>
          <Link to="/settings" onClick={() => setOpen(false)}>Settings & definitions</Link>
        </div>
      )}
    </div>
  );
}

function Breadcrumbs() {
  const { pathname } = useLocation();
  const cur = FLAT.find((n) => pathname === n.to || pathname.startsWith(n.to + "/"));
  const detail = cur && pathname.startsWith(cur.to + "/") ? decodeURIComponent(pathname.slice(cur.to.length + 1)) : null;
  return (
    <div className="crumbs" aria-label="Breadcrumb">
      <span className="hide-sm">NovaBank</span><span className="hide-sm">/</span>
      {cur ? (detail ? <><Link to={cur.to} className="link">{cur.label}</Link><span>/</span><b>{detail}</b></> : <b>{cur.label}</b>) : <b>Not found</b>}
    </div>
  );
}

export default function Shell() {
  const [collapsed, setCollapsed] = useState(() => { try { return localStorage.getItem("nb_collapsed") === "1"; } catch { return false; } });
  const [drawer, setDrawer] = useState(false);
  const { theme, setTheme } = useTheme();
  const demoMeta = useApi("/v1/meta").data;
  const loc = useLocation();
  useEffect(() => setDrawer(false), [loc.pathname]);
  const cur = FLAT.find((n) => loc.pathname === n.to || loc.pathname.startsWith(n.to + "/"));
  const toggle = () => { setCollapsed(!collapsed); try { localStorage.setItem("nb_collapsed", collapsed ? "0" : "1"); } catch { /* ignore */ } };
  return (
    <div className={"app" + (collapsed ? " collapsed" : "") + (drawer ? " drawer" : "")}>
      <aside className="sidebar" aria-label="Primary">
        <Link to="/overview" className="brand" aria-label="NovaBank home"><LogoMark size={38} /><div className="wm"><b>Nova<i>Bank</i></b><small>Analytics Intelligence</small></div></Link>
        <nav className="nav">
          {NAV.map((n, i) => n.group ? <div className="group" key={i}>{n.group}</div> : (
            <NavLink key={n.to} to={n.to} title={n.label} className={({ isActive }) => (isActive ? "active" : "")}><n.icon size={18} /><span>{n.label}</span></NavLink>
          ))}
        </nav>
        <div className="side-foot only-desktop">
          <button className="btn sm" style={{ width: "100%", justifyContent: "center" }} onClick={toggle} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
            {collapsed ? <ChevronsRight size={16} /> : <><ChevronsLeft size={16} /><span>Collapse</span></>}
          </button>
        </div>
      </aside>
      <div className="scrim" onClick={() => setDrawer(false)} />
      <div className="main">
        <header className="topbar">
          <button className="icon-btn only-mobile" aria-label="Open menu" onClick={() => setDrawer(true)}><Menu size={18} /></button>
          <Breadcrumbs />
          <div className="spacer" />
          <GlobalSearch />
          {cur?.range && <div className="hide-xs"><RangeControl /></div>}
          {demoMeta?.demo && <span className="badge simulated demo-chip" title="A read-only snapshot of the synthetic data; scoring and write-backs are switched off">Hosted demo · read-only</span>}
          <Notifications />
          <button className="icon-btn" aria-label="Toggle theme" title={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"} onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>{theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}</button>
          <Profile />
        </header>
        <main className="content">
          {cur?.range && <div className="only-mobile" style={{ marginBottom: 12 }}><RangeControl /></div>}
          <Suspense fallback={<div style={{ display: "grid", gap: 12 }}><Skeleton h={34} w="40%" /><Skeleton h={120} /><Skeleton h={300} /></div>}>
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/overview" element={<Overview />} />
              <Route path="/payments" element={<Payments />} />
              <Route path="/fraud" element={<Fraud />} />
              <Route path="/customers" element={<Customers />} />
              <Route path="/customers/:id" element={<CustomerDetail />} />
              <Route path="/merchants" element={<Merchants />} />
              <Route path="/merchants/:id" element={<Merchants />} />
              <Route path="/branches" element={<Branches />} />
              <Route path="/branches/:id" element={<Branches />} />
              <Route path="/explorer" element={<Explorer />} />
              <Route path="/global" element={<GlobalIntel />} />
              <Route path="/benchmarks" element={<Benchmarks />} />
              <Route path="/engineering" element={<Engineering />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<div className="state"><h2>Page not found</h2><Link className="link" to="/overview">Go to the overview</Link></div>} />
            </Routes>
          </Suspense>
        </main>
      </div>
    </div>
  );
}
