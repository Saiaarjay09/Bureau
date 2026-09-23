import type { Lead, LeadsPage, Regions } from './types'

class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    ...options,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options.headers },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(res.status, body.detail || res.statusText)
  }
  return res.json()
}

export { ApiError }

export const api = {
  authStatus: () => request<{ credentials_configured: boolean }>('/api/auth/status'),
  login: (username: string, password: string) =>
    request<{ username: string }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  me: () => request<{ username: string }>('/api/auth/me'),

  regions: () => request<Regions>('/api/regions'),
  cities: (params: { lead_type: string; continent?: string; country?: string; q?: string }) =>
    request<{ cities: string[] }>('/api/regions/cities?' + new URLSearchParams(cleanParams(params))),

  leads: (params: Record<string, string | number | boolean | undefined>) =>
    request<LeadsPage>('/api/leads?' + new URLSearchParams(cleanParams(params))),
  toggleStar: (id: number) => request<Lead>(`/api/leads/${id}/star`, { method: 'POST' }),
  exportUrl: (params: Record<string, string | number | boolean | undefined>) =>
    '/api/leads/export?' + new URLSearchParams(cleanParams(params)).toString(),

  ingestStatus: () => request<{ firecrawl_configured: boolean; last_run: Record<string, string> }>(
    '/api/ingest/status',
  ),
  ingestJobs: () => request('/api/ingest/jobs', { method: 'POST' }),
  ingestBusiness: (industry: string, region: string) =>
    request<{ created: number; updated: number }>('/api/ingest/business', {
      method: 'POST',
      body: JSON.stringify({ industry, region }),
    }),
}

function cleanParams(params: Record<string, string | number | boolean | undefined>) {
  const out: Record<string, string> = {}
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '' && value !== null) out[key] = String(value)
  }
  return out
}
