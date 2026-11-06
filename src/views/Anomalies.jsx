import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import { Badge, Card, Empty, cap } from "../ui.jsx";

export default function Anomalies({ version }) {
  const [rows, setRows] = useState([]);
  const [sev, setSev] = useState("");
  const [machine, setMachine] = useState("");

  useEffect(() => {
    api.anomalies(sev).then(setRows).catch(() => setRows([]));
  }, [sev, version]);

  const machines = [...new Set(rows.map((r) => r.machine))].sort();
  const shown = rows.filter((r) => !machine || r.machine === machine);

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Anomalies</h1>
        <div className="flex gap-2 text-sm">
          <select value={sev} onChange={(e) => setSev(e.target.value)} className="rounded border border-line bg-white px-3 py-2">
            <option value="">All severities</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </select>
          <select value={machine} onChange={(e) => setMachine(e.target.value)} className="rounded border border-line bg-white px-3 py-2">
            <option value="">All machines</option>
            {machines.map((m) => <option key={m}>{m}</option>)}
          </select>
        </div>
      </div>
      <p className="text-sm text-slate-500">Every flag comes from a fixed rule and shows the numbers behind it. No AI is involved in detection.</p>
      {shown.length === 0 ? <Empty>No anomalies found.</Empty> : (
        <Card>
          <ul className="divide-y divide-line">
            {shown.map((a) => (
              <li key={a.id} className="flex items-start gap-3 py-3">
                <Badge sev={a.severity} />
                <div className="min-w-0 flex-1">
                  <div className="font-medium">{a.message}</div>
                  <div className="text-xs text-slate-500">{a.evidence}</div>
                  <div className="mt-0.5 text-xs text-slate-400">{a.machine} · {a.date} {cap(a.shift)} · rule: {a.rule} · <code>{a.source_ref}</code></div>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}
