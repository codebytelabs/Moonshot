const API = process.env.NEXT_PUBLIC_BACKEND_URL || "";

export async function apiFetch(path: string, opts?: RequestInit) {
  const res = await fetch(`${API}${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", ...opts?.headers },
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

export function getWsUrl() {
  const base = API.replace(/^http/, "ws");
  return `${base}/api/ws`;
}
