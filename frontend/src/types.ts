export type LeadType = 'job' | 'business'

export interface Lead {
  id: number
  lead_type: LeadType
  source: string
  title: string
  company: string
  company_domain: string | null
  url: string | null
  continent: string | null
  country: string | null
  city: string | null
  remote_type: string | null
  seniority: string | null
  industry: string | null
  contact_path: string | null
  company_size: string | null
  funding_stage: string | null
  signal: string | null
  tags: string[]
  fit_score: number | null
  fit_reason: string | null
  council_status: string | null
  council_score: number | null
  posted_date: string | null
  starred: boolean
}

export interface CouncilVerdict {
  score?: number
  match_pct?: number
  verdict?: string
  confidence?: string
  summary?: string
  blocking_gaps?: string[]
  error?: string
}

export interface LeadDetail extends Lead {
  description: string | null
  council_match_pct: number | null
  council: CouncilVerdict | null
}

export interface MatchStatus {
  cv: { present: boolean; chars: number; updated_at: string | null }
  sabha: { available: boolean; council_size?: number; error?: string }
  screening: { running: boolean; screened: number; remaining: number; paused_for_council: boolean }
}

export interface LeadsPage {
  total: number
  items: Lead[]
}

export interface Regions {
  continents: Record<string, string[]>
}

export type SortOrder = 'newest' | 'oldest' | 'company' | 'fit'
