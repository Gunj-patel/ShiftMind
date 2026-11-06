async function req(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {}
    throw new Error(detail);
  }
  return res.json();
}

const json = (method, body) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => req("/api/health"),
  shifts: () => req("/api/shifts"),
  report: (date, shift) => req(`/api/report?date=${date}&shift=${shift}`),
  anomalies: (severity) => req(`/api/anomalies${severity ? `?severity=${severity}` : ""}`),
  trends: (machine) => req(`/api/trends${machine ? `?machine=${machine}` : ""}`),
  machines: () => req("/api/machines"),
  documents: () => req("/api/documents"),
  ask: (question) => req("/api/ask", json("POST", { question })),
  toggleAction: (id, done) => req(`/api/actions/${id}`, json("PATCH", { done })),
  uploadText: (text, label) => req("/api/upload-text", json("POST", { text, label })),
  reset: () => req("/api/data", { method: "DELETE" }),
  upload: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return req("/api/upload", { method: "POST", body: fd });
  },
};
