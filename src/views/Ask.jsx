import React, { useState } from "react";
import { api } from "../api.js";
import { Card } from "../ui.jsx";

const EXAMPLES = [
  "Why was M-102 down in the last week?",
  "Which machines had quality problems on the night shift?",
  "Is there any pending maintenance?",
  "How much downtime did M-103 have?",
];

export default function Ask() {
  const [q, setQ] = useState("");
  const [log, setLog] = useState([]);
  const [busy, setBusy] = useState(false);

  const submit = async (question) => {
    if (!question.trim()) return;
    setBusy(true);
    try {
      const r = await api.ask(question);
      setLog((l) => [{ q: question, r }, ...l]);
      setQ("");
    } catch (e) {
      setLog((l) => [{ q: question, error: e.message }, ...l]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h1 className="text-2xl font-semibold">Ask ShiftMind</h1>
      <p className="text-sm text-slate-500">Answers are built only from stored shift records, and every answer lists the records it came from.</p>
      <form onSubmit={(e) => { e.preventDefault(); submit(q); }} className="flex gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. Why was M-102 down this week?" className="flex-1 rounded border border-line bg-white px-3 py-2" />
        <button disabled={busy} className="rounded bg-brand px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">{busy ? "…" : "Ask"}</button>
      </form>
      <div className="flex flex-wrap gap-2">
        {EXAMPLES.map((e) => (
          <button key={e} onClick={() => submit(e)} className="rounded-full border border-line bg-white px-3 py-1 text-xs hover:bg-slate-50">{e}</button>
        ))}
      </div>
      {log.map((item, i) => (
        <Card key={i} title={item.q}>
          {item.error ? <p className="text-crit">{item.error}</p> : (
            <>
              <p className="leading-relaxed">{item.r.answer}</p>
              <div className="mt-1 text-xs text-slate-500">{item.r.answer_source === "llm" ? "AI-phrased" : "Rule-based"} answer</div>
              {item.r.sources.length > 0 && (
                <details className="mt-3" open={i === 0}>
                  <summary className="cursor-pointer text-sm font-semibold">Sources ({item.r.sources.length})</summary>
                  <ol className="mt-2 list-decimal space-y-1 pl-5 text-xs text-slate-600">
                    {item.r.sources.map((s) => (
                      <li key={s.record_id}><b>{s.label}</b> — {s.excerpt} <code className="text-slate-400">({s.ref})</code></li>
                    ))}
                  </ol>
                </details>
              )}
            </>
          )}
        </Card>
      ))}
    </>
  );
}
