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
  posted_date: string | null
  starred: boolean
}

export interface LeadsPage {
  total: number
  items: Lead[]
}

export interface Regions {
  continents: Record<string, string[]>
}

export type SortOrder = 'newest' | 'oldest' | 'company'
