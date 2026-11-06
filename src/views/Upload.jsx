import React, { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { Badge, Card } from "../ui.jsx";

export default function Upload({ onChange }) {
  const [docs, setDocs] = useState([]);
  const [busy, setBusy] = useState(false);
  const [last, setLast] = useState(null);
  const [err, setErr] = useState("");
  const [text, setText] = useState("");
  const [drag, setDrag] = useState(false);
  const input = useRef();

  const load = () => api.documents().then(setDocs).catch(() => {});
  useEffect(() => { load(); }, []);

  const run = async (fn) => {
    setBusy(true);
    setErr("");
    try {
      setLast(await fn());
      await load();
      onChange();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const onFiles = async (files) => {
    for (const f of files) await run(() => api.upload(f));
  };

  return (
    <>
      <h1 className="text-2xl font-semibold">Upload logs</h1>
      <Card title="Excel, CSV, PDF or text reports">
        <div
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); onFiles([...e.dataTransfer.files]); }}
          onClick={() => input.current.click()}
          className={`cursor-pointer rounded-lg border-2 border-dashed p-10 text-center text-sm ${drag ? "border-brand bg-blue-50" : "border-line"}`}
        >
          {busy ? "Reading and checking…" : "Drop files here or click to choose"}
          <input ref={input} type="file" multiple hidden accept=".csv,.xlsx,.xls,.pdf,.txt" onChange={(e) => onFiles([...e.target.files])} />
        </div>
        <p className="mt-2 text-xs text-slate-500">Column names are matched flexibly (e.g. "Produced", "Output", "Actual"). Rows that cannot be understood are listed, never guessed.</p>
        {err && <div className="mt-3 rounded border border-red-200 bg-red-50 p-3 text-sm text-crit">{err}</div>}
        {last && (
          <div className="mt-3 rounded border border-line bg-slate-50 p-3 text-sm">
            <b>{last.filename}</b>: {last.rows_parsed} rows read, {last.rows_rejected} rejected, {last.anomalies_total} flags in total.
            {last.notes?.map((n, i) => <div key={i} className="text-xs text-warn">{n}</div>)}
            {last.rejected?.slice(0, 5).map((r, i) => <div key={i} className="text-xs text-crit">{r.ref}: {r.reason}</div>)}
          </div>
        )}
      </Card>

      <Card title="Or paste a handwritten / messaged report">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={7}
          placeholder={"Date: 2026-11-03\nShift: Morning\n\nMachine: M-102\nTarget: 500\nActual: 320\nDowntime: 95\nReason: Motor overheating\nMaintenance: Pending"}
          className="w-full rounded border border-line p-3 font-mono text-sm"
        />
        <button
          disabled={!text.trim() || busy}
          onClick={() => run(() => api.uploadText(text, "pasted-text")).then(() => setText(""))}
          className="mt-2 rounded bg-brand px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
        >
          Analyse text
        </button>
      </Card>

      <Card
        title="Uploaded documents"
        right={<button className="text-xs text-crit underline" onClick={() => window.confirm("Delete all data?") && run(api.reset)}>Clear all data</button>}
      >
        {docs.length === 0 ? <p className="text-sm text-slate-500">Nothing uploaded yet. Sample files are in the repo's sample_data folder.</p> : (
          <ul className="divide-y divide-line text-sm">
            {docs.map((d) => (
              <li key={d.id} className="flex items-center justify-between py-2">
                <span>{d.filename} <Badge>{d.kind}</Badge></span>
                <span className="text-xs text-slate-500">{d.rows_parsed} rows · {d.rows_rejected} rejected</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
