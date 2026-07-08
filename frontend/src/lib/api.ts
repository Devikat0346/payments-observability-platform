export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL ??
  API_URL.replace(/^http/, "ws") + "/ws/live";

export async function fetchRecentTransactions(limit = 50) {
  const res = await fetch(`${API_URL}/api/transactions/recent?limit=${limit}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Failed to fetch transactions: ${res.status}`);
  return res.json();
}

export async function fetchMetricsSummary() {
  const res = await fetch(`${API_URL}/api/metrics/summary`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Failed to fetch metrics: ${res.status}`);
  return res.json();
}

export async function fetchIncidents(activeOnly = false) {
  const res = await fetch(
    `${API_URL}/api/incidents?active_only=${activeOnly}`,
    { cache: "no-store" }
  );
  if (!res.ok) throw new Error(`Failed to fetch incidents: ${res.status}`);
  return res.json();
}
