const BASE = "/api/v1";

export function getApiKey(): string {
  return localStorage.getItem("apiKey") ?? "";
}

export async function api<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: {
      "X-API-Key": getApiKey(),
      ...(opts.body && !(opts.body instanceof FormData)
        ? { "Content-Type": "application/json" } : {}),
      ...opts.headers,
    },
  });
  if (res.status === 401) throw new Error("API key inválida — configure em Mais > Config");
  if (!res.ok) throw new Error(`Erro ${res.status}: ${await res.text()}`);
  return res.json();
}
