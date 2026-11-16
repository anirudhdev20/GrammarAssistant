function apiBase() {
  const param = new URLSearchParams(window.location.search).get("api");
  if (param) return param.replace(/\/$/, "");
  if (window.GA_API_BASE) return String(window.GA_API_BASE).replace(/\/$/, "");
  try {
    return (localStorage.getItem("ga_api_base") || "").replace(/\/$/, "");
  } catch {
    return "";
  }
}

async function request(path, options = {}) {
  const response = await fetch(`${apiBase()}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((item) => item.msg).join("; ");
    } catch {
      /* keep default message */
    }
    throw new Error(detail);
  }
  return response.json();
}

export function analyze(text, options = {}, signal) {
  return request("/api/analyze", {
    method: "POST",
    body: JSON.stringify({ text, include_stats: true, ...options }),
    signal,
  });
}

export function rewrite(text, start, end, replacement) {
  return request("/api/rewrite", {
    method: "POST",
    body: JSON.stringify({ text, start, end, replacement }),
  });
}

export async function exportPdf(text, title = "Grammar Assistant") {
  const response = await fetch(`${apiBase()}/api/export/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, title }),
  });
  if (!response.ok) {
    let detail = `PDF export failed with status ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* keep default message */
    }
    throw new Error(detail);
  }
  return response.blob();
}

export async function importPdf(file) {
  const formData = new FormData();
  formData.append("file", file, file.name);
  const response = await fetch(`${apiBase()}/api/import/pdf`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    let detail = `PDF import failed with status ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* keep default message */
    }
    throw new Error(detail);
  }
  return response.json();
}

export async function checkHealth() {
  return request("/health");
}
