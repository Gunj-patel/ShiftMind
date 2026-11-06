import React from "react";

export const SEV = {
  critical: "bg-red-50 text-crit border-red-200",
  warning: "bg-amber-50 text-warn border-amber-200",
  info: "bg-slate-100 text-slate-600 border-slate-200",
};

export function Badge({ sev, children }) {
  return (
    <span className={`inline-block rounded border px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ${SEV[sev] || SEV.info}`}>
      {children || sev}
    </span>
  );
}

export function Card({ title, right, children, className = "" }) {
  return (
    <section className={`rounded-lg border border-line bg-panel p-5 ${className}`}>
      {(title || right) && (
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">{title}</h2>
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export function Kpi({ label, value, sub, tone }) {
  const color = tone === "bad" ? "text-crit" : tone === "warn" ? "text-warn" : tone === "good" ? "text-ok" : "text-ink";
  return (
    <div className="rounded-lg border border-line bg-panel p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 text-3xl font-semibold tabular-nums ${color}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-500">{sub}</div>}
    </div>
  );
}

export const fmt = (v, d = 0) => (v === null || v === undefined ? "—" : Number(v).toLocaleString(undefined, { maximumFractionDigits: d }));
export const pct = (v) => (v === null || v === undefined ? "—" : `${Math.round(v * 100)}%`);
export const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

export function Empty({ children }) {
  return <div className="rounded-lg border border-dashed border-line p-8 text-center text-sm text-slate-500">{children}</div>;
}
