import React, { useEffect, useState } from "react";
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api.js";
import { Card, Empty } from "../ui.jsx";

export default function Trends({ version }) {
  const [machine, setMachine] = useState("");
  const [machines, setMachines] = useState([]);
  const [data, setData] = useState([]);

  useEffect(() => { api.machines().then(setMachines).catch(() => {}); }, [version]);
  useEffect(() => { api.trends(machine).then(setData).catch(() => setData([])); }, [machine, version]);

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Trends</h1>
        <select value={machine} onChange={(e) => setMachine(e.target.value)} className="rounded border border-line bg-white px-3 py-2 text-sm">
          <option value="">All machines</option>
          {machines.map((m) => <option key={m}>{m}</option>)}
        </select>
      </div>
      {data.length === 0 ? <Empty>No data yet.</Empty> : (
        <>
          <Card title="Daily production vs target (units)">
            <div className="h-72">
              <ResponsiveContainer>
                <ComposedChart data={data}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#dde3ec" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="actual" name="Actual" fill="#1d4ed8" />
                  <Line dataKey="target" name="Target" stroke="#14213d" strokeDasharray="5 4" dot={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card title="Daily downtime (minutes) and rejects (units)">
            <div className="h-72">
              <ResponsiveContainer>
                <ComposedChart data={data}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#dde3ec" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="downtime" name="Downtime (min)" fill="#b45309" />
                  <Line dataKey="rejected" name="Rejected units" stroke="#c62828" dot={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </>
      )}
    </>
  );
}
