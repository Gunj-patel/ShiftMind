import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import { Badge, Card, Empty, Kpi, cap, fmt, pct } from "../ui.jsx";

const PRI = { high: "critical", medium: "warning", low: "info" };

export default function Report({ shifts, version, goUpload }) {
  const [sel, setSel] = useState("");
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [open, setOpen] = useState(null);

  useEffect(() => {
    if (shifts.length && !sel) setSel(`${shifts[0].date}|${shifts[0].shift}`);
  }, [shifts, sel]);

  useEffect(() => {
    if (!sel) return;
    const [d, s] = sel.split("|");
    setErr("");
    api.report(d, s).then(setData).catch((e) => setErr(e.message));
  }, [sel, version]);

  if (!shifts.length)
    return (
      <Empty>
        No shift data yet.{" "}
        <button className="font-semibold text-brand underline" onClick={goUpload}>
          Upload logs
        </button>{" "}
        or load the sample data.
      </Empty>
    );

  const f = data?.facts;
  const toggle = async (a) => {
    await api.toggleAction(a.id, !a.done);
    setData((d) => ({ ...d, actions: d.actions.map((x) => (x.id === a.id ? { ...x, done: !x.done } : x)) }));
  };

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Shift report</h1>
        <select value={sel} onChange={(e) => setSel(e.target.value)} className="rounded border border-line bg-white px-3 py-2 text-sm">
          {shifts.map((s) => (
            <option key={s.date + s.shift} value={`${s.date}|${s.shift}`}>
              {s.date} · {cap(s.shift)}
            </option>
          ))}
        </select>
      </div>
      {err && <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-crit">{err}</div>}
      {f && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Kpi label="Target" value={fmt(f.total_target)} sub="units" />
            <Kpi label="Actual" value={fmt(f.total_actual)} sub="units" />
            <Kpi label="Achievement" value={pct(f.achievement)} tone={f.achievement < 0.7 ? "bad" : f.achievement < 0.9 ? "warn" : "good"} />
            <Kpi label="Downtime" value={`${fmt(f.total_downtime_min)} min`} tone={f.total_downtime_min >= 120 ? "bad" : f.total_downtime_min >= 60 ? "warn" : undefined} />
          </div>

          <Card
            title="Shift summary"
            right={
              <div className="flex items-center gap-2">
                <Badge sev={f.status === "attention" ? "warning" : "info"}>{f.status === "attention" ? "Attention required" : "Normal"}</Badge>
                <span className="text-xs text-slate-500">{data.summary_source === "llm" ? "AI-written" : "Rule-based"} text</span>
              </div>
            }
          >
            <p className="leading-relaxed">{data.summary}</p>
          </Card>

          <Card title={`Handover for ${cap(data.incoming_shift)} shift`} right={<span className="text-xs text-slate-500">{data.actions.filter((a) => a.done).length}/{data.actions.length} done</span>}>
            {data.actions.length === 0 ? (
              <p className="text-sm text-slate-500">No actions generated — nothing flagged in this shift.</p>
            ) : (
              <ul className="divide-y divide-line">
                {data.actions.map((a) => (
                  <li key={a.id} className="flex items-start gap-3 py-3">
                    <input type="checkbox" checked={a.done} onChange={() => toggle(a)} className="mt-1 h-4 w-4" aria-label="Mark done" />
                    <div className="min-w-0 flex-1">
                      <div className={a.done ? "text-slate-400 line-through" : ""}>{a.action}</div>
                      <div className="mt-0.5 text-xs text-slate-500">Why: {a.reason}</div>
                    </div>
                    <Badge sev={PRI[a.priority]}>{a.priority}</Badge>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-3 border-t border-line pt-3 text-xs text-slate-500">
              ShiftMind lists what to check. A person must decide whether a machine is safe to run.
            </p>
          </Card>

          <Card title="Machines">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs uppercase text-slate-500">
                    <th className="py-2 pr-3">Machine</th>
                    <th className="pr-3 text-right">Target</th>
                    <th className="pr-3 text-right">Actual</th>
                    <th className="pr-3 text-right">Ach.</th>
                    <th className="pr-3 text-right">Down (min)</th>
                    <th className="pr-3">Flags</th>
                  </tr>
                </thead>
                <tbody>
                  {f.machines.map((m) => (
                    <React.Fragment key={m.record_id}>
                      <tr className="cursor-pointer border-b border-line/60 hover:bg-slate-50" onClick={() => setOpen(open === m.record_id ? null : m.record_id)}>
                        <td className="py-2 pr-3 font-medium">{m.machine}</td>
                        <td className="pr-3 text-right tabular-nums">{fmt(m.target)}</td>
                        <td className="pr-3 text-right tabular-nums">{fmt(m.actual)}</td>
                        <td className="pr-3 text-right tabular-nums">{pct(m.achievement)}</td>
                        <td className="pr-3 text-right tabular-nums">{fmt(m.downtime_min)}</td>
                        <td className="pr-3">
                          {m.anomalies.length === 0 ? <span className="text-slate-400">—</span> : (
                            <span className="flex flex-wrap gap-1">
                              {m.anomalies.slice(0, 3).map((a, i) => <Badge key={i} sev={a.severity}>{a.rule.replace(/_/g, " ")}</Badge>)}
                            </span>
                          )}
                        </td>
                      </tr>
                      {open === m.record_id && (
                        <tr className="bg-slate-50">
                          <td colSpan={6} className="px-3 py-3 text-xs text-slate-600">
                            <div className="mb-1">Source: <code>{m.source_ref}</code>{m.operator && ` · recorded by ${m.operator}`}</div>
                            {m.downtime_reason && <div>Downtime reason: {m.downtime_reason}</div>}
                            {m.notes && <div>Note: {m.notes}</div>}
                            {m.anomalies.map((a, i) => (
                              <div key={i} className="mt-1"><b>{a.message}</b> — {a.evidence}</div>
                            ))}
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {f.missing_reports.length > 0 && (
            <Card title="Missing reports">
              <ul className="list-disc pl-5 text-sm">
                {f.missing_reports.map((m, i) => <li key={i}>{m.message}</li>)}
              </ul>
            </Card>
          )}
        </>
      )}
    </>
  );
}
