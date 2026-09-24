import type { Lead, LeadDetail, LeadsPage, MatchStatus, Regions } from './types'

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
  signup: (username: string, password: string) =>
    request<{ username: string; recovery_phrase: string }>('/api/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  login: (username: string, password: string) =>
    request<{ username: string }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  recover: (recovery_phrase: string, new_password: string) =>
    request<{ ok: boolean }>('/api/auth/recover', {
      method: 'POST',
      body: JSON.stringify({ recovery_phrase, new_password }),
    }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  me: () => request<{ username: string }>('/api/auth/me'),

  regions: () => request<Regions>('/api/regions'),
  cities: (params: { lead_type: string; continent?: string; country?: string; q?: string }) =>
    request<{ cities: string[] }>('/api/regions/cities?' + new URLSearchParams(cleanParams(params))),

  leads: (params: Record<string, string | number | boolean | undefined>) =>
    request<LeadsPage>('/api/leads?' + new URLSearchParams(cleanParams(params))),
  lead: (id: number) => request<LeadDetail>(`/api/leads/${id}`),
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
  ingestJobSearch: (role: string, region: string) =>
    request<{ created: number; updated: number }>('/api/ingest/job_search', {
      method: 'POST',
      body: JSON.stringify({ role, region }),
    }),

  matchStatus: () => request<MatchStatus>('/api/match/status'),
  uploadCv: async (file: File) => {
    const body = new FormData()
    body.append('file', file)
    // Deliberately not using request(): it sets Content-Type: application/json,
    // and a multipart upload needs the browser to set that header itself so it
    // can include the boundary.
    const res = await fetch('/api/match/cv/upload', { method: 'POST', credentials: 'include', body })
    if (!res.ok) {
      const payload = await res.json().catch(() => ({}))
      throw new ApiError(res.status, payload.detail || res.statusText)
    }
    return (await res.json()) as { chars: number; rescoring: number; parsed_from: string; filename: string }
  },
  putCv: (text: string) =>
    request<{ present: boolean; chars: number; rescoring: number }>('/api/match/cv', {
      method: 'PUT',
      body: JSON.stringify({ text }),
    }),
  deleteCv: () => request<{ ok: boolean }>('/api/match/cv', { method: 'DELETE' }),
  startCouncil: (leadId: number) =>
    request<{ status: string }>(`/api/match/council/${leadId}`, { method: 'POST' }),
}

function cleanParams(params: Record<string, string | number | boolean | undefined>) {
  const out: Record<string, string> = {}
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '' && value !== null) out[key] = String(value)
  }
  return out
}
