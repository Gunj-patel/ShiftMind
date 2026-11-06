import React, { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import Report from "./views/Report.jsx";
import Upload from "./views/Upload.jsx";
import Anomalies from "./views/Anomalies.jsx";
import Ask from "./views/Ask.jsx";
import Trends from "./views/Trends.jsx";

const TABS = [
  ["report", "Shift report"],
  ["anomalies", "Anomalies"],
  ["trends", "Trends"],
  ["ask", "Ask ShiftMind"],
  ["upload", "Upload logs"],
];

export default function App() {
  const [tab, setTab] = useState("report");
  const [shifts, setShifts] = useState([]);
  const [health, setHealth] = useState(null);
  const [version, setVersion] = useState(0); // bump after uploads to refresh every view

  const refresh = useCallback(() => {
    api.shifts().then(setShifts).catch(() => setShifts([]));
    setVersion((v) => v + 1);
  }, []);

  useEffect(() => {
    refresh();
    api.health().then(setHealth).catch(() => setHealth({ status: "down" }));
  }, [refresh]);

  const down = health?.status === "down";

  return (
    <div className="min-h-screen md:flex">
      <aside className="border-b border-line bg-ink text-white md:min-h-screen md:w-60 md:border-b-0">
        <div className="px-5 py-5">
          <div className="text-xl font-semibold tracking-tight">ShiftMind</div>
          <div className="text-xs text-slate-300">Industrial shift intelligence</div>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:pb-0">
          {TABS.map(([id, label]) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`whitespace-nowrap rounded px-3 py-2 text-left text-sm transition ${
                tab === id ? "bg-white/15 font-semibold" : "text-slate-300 hover:bg-white/10"
              }`}
            >
              {label}
            </button>
          ))}
        </nav>
        <div className="hidden px-5 py-4 text-xs text-slate-300 md:block">
          {health && !down && (
            <div>
              AI narration: <b>{health.llm_enabled ? "LLM on" : "rules only"}</b>
              <div className="mt-1 opacity-70">Numbers always come from rules, never the LLM.</div>
            </div>
          )}
        </div>
      </aside>

      <main className="mx-auto w-full max-w-6xl flex-1 space-y-4 p-4 md:p-8">
        {down && (
          <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-crit">
            Cannot reach the ShiftMind API. Start the backend (see README) and reload.
          </div>
        )}
        {tab === "report" && <Report shifts={shifts} version={version} goUpload={() => setTab("upload")} />}
        {tab === "anomalies" && <Anomalies version={version} />}
        {tab === "trends" && <Trends version={version} />}
        {tab === "ask" && <Ask version={version} />}
        {tab === "upload" && <Upload onChange={refresh} />}
      </main>
    </div>
  );
}
