"""Sample leads for previewing the UI before real sources are wired up.
Seeded via scripts/seed_mock_data.py — never used by the real app at runtime."""

from datetime import datetime, timedelta

from .regions import COUNTRY_TO_CONTINENT


def _c(country: str) -> str:
    return COUNTRY_TO_CONTINENT.get(country, "")


def mock_jobs() -> list[dict]:
    now = datetime.utcnow()
    rows = [
        ("Senior Backend Engineer", "Nordwind Labs", "Germany", "Berlin", "remote", "senior",
         "51-200", "Series B", "Hiring 5 similar backend roles this month"),
        ("Product Designer", "Kiritsu", "Japan", "Tokyo", "hybrid", "mid",
         "11-50", "Seed", "First design hire after a $4M seed round"),
        ("Data Platform Lead", "Meridian Analytics", "United States", "Austin", "remote", "lead",
         "201-500", "Series C", "Opened a new data team; 3 open reqs"),
        ("Frontend Engineer (React)", "Solara Health", "Canada", "Toronto", "remote", "mid",
         "51-200", "Series A", "Doubling eng headcount this quarter"),
        ("DevOps Engineer", "Vantage Cloud", "United Kingdom", "London", "onsite", "senior",
         "201-500", "Series B", "Migrating to multi-region infra"),
        ("Machine Learning Engineer", "Aperture AI", "United States", "San Francisco", "remote",
         "senior", "11-50", "Seed", "Just closed $8M seed, first 3 ML hires"),
        ("Customer Success Manager", "Fenwick Systems", "Australia", "Sydney", "hybrid", "mid",
         "51-200", "Series A", "Expanding into APAC market"),
        ("Backend Engineer (Go)", "Rivet Payments", "Singapore", "Singapore", "remote", "mid",
         "51-200", "Series B", "New payments license, scaling infra team"),
        ("Growth Marketing Manager", "Bloomfield", "Brazil", "Sao Paulo", "hybrid", "mid",
         "11-50", "Seed", "First marketing hire post-seed"),
        ("Site Reliability Engineer", "Northstar Cloud", "United States", "Seattle", "remote",
         "senior", "501-1000", "Series D", "Hiring 4 SRE roles for new region"),
    ]
    out = []
    for i, (title, company, country, city, remote, seniority, size, funding, signal) in enumerate(rows):
        out.append({
            "lead_type": "job",
            "source": "mock",
            "external_id": f"mock-job-{i}",
            "title": title,
            "company": company,
            "company_domain": company.lower().replace(" ", "") + ".com",
            "url": "https://example.com/jobs/" + str(i),
            "continent": _c(country),
            "country": country,
            "city": city,
            "remote_type": remote,
            "seniority": seniority,
            "company_size": size,
            "funding_stage": funding,
            "signal": signal,
            "tags": ["mock"],
            "posted_date": now - timedelta(days=i),
        })
    return out


def mock_businesses() -> list[dict]:
    now = datetime.utcnow()
    rows = [
        ("Halcyon Robotics", "United States", "Boston", "Robotics", "51-200", "Series B",
         "Raised $22M Series B two weeks ago", "hello@halcyonrobotics.com"),
        ("Verdant Foods", "Netherlands", "Amsterdam", "FoodTech", "11-50", "Seed",
         "New VP of Sales hired last month", "contact@verdantfoods.nl"),
        ("Cobalt Freight", "United States", "Chicago", "Logistics", "201-500", "Series C",
         "Opened a new Midwest distribution hub", "info@cobaltfreight.com"),
        ("Lumen Health", "United Kingdom", "Manchester", "HealthTech", "51-200", "Series A",
         "Hiring 8 roles across eng and clinical ops", "team@lumenhealth.co.uk"),
        ("Ostrava Systems", "Czechia", "Prague", "Cybersecurity", "11-50", "Seed",
         "Announced expansion into the DACH market", "hi@ostravasystems.com"),
        ("Kestrel Insurance", "Singapore", "Singapore", "InsurTech", "201-500", "Series B",
         "New CTO appointed, rebuilding platform team", "partnerships@kestrelinsurance.sg"),
        ("Monarch Materials", "Canada", "Vancouver", "Manufacturing", "501-1000", "Series D",
         "Announced a new production facility", "sales@monarchmaterials.ca"),
        ("Aurelia Studio", "France", "Paris", "Creative/Agency", "11-50", "Bootstrapped",
         "Won 3 new enterprise clients this quarter", "bonjour@aureliastudio.fr"),
    ]
    out = []
    for i, (company, country, city, industry, size, funding, signal, contact) in enumerate(rows):
        out.append({
            "lead_type": "business",
            "source": "mock",
            "external_id": f"mock-biz-{i}",
            "title": f"{industry} opportunity: {company}",
            "company": company,
            "company_domain": contact.split("@")[-1],
            "url": "https://example.com/companies/" + str(i),
            "continent": _c(country),
            "country": country,
            "city": city,
            "industry": industry,
            "contact_path": contact,
            "company_size": size,
            "funding_stage": funding,
            "signal": signal,
            "tags": ["mock"],
            "posted_date": now - timedelta(days=i * 2),
        })
    return out
