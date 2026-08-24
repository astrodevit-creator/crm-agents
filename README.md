# crm-agents

A library of Python agents for building and maintaining a CRM of businesses:
find companies by niche, enrich them with contact intelligence and social
presence, deduplicate, query/export, and orchestrate the whole pipeline.

> Original project. A practical toolkit for lead-generation and CRM hygiene
> automation. Agents are modular classes built on a small shared `Agent` core.

## Overview

`crm-agents` provides reusable agents that operate on a shared SQLite-backed
CRM. Point the discovery agent at a niche, and it will find candidate
companies, enrich them with emails/phones/socials, score and dedupe, and let
you query or export the result as CSV/XLSX/JSON.

## Agents

| Module | Class | What it does |
| --- | --- | --- |
| `agent_company_finder.py` | `CompanyFinder` | Searches the web for companies in a niche; guesses and validates domains; saves candidates. |
| `agent_contact_intel.py` | `ContactIntel` | Enriches a company: host liveness, subpage discovery, email/phone/WhatsApp extraction and validation. |
| `agent_social_scanner.py` | `SocialScanner` | Constructs and verifies social profile URLs (Facebook/Instagram/etc.) for a company. |
| `agent_deduper.py` | `Deduper` | Finds duplicate companies (e.g. exact domain), merges records, batches dedupe. |
| `agent_crm_query.py` | `CRMQuery` | Lists/filters companies, fetches full records, exports CSV/XLSX/JSON. |
| `agent_orchestrator.py` | `CEOAgent` | Runs the end-to-end pipeline and a recurring loop; produces a dashboard summary. |
| `core.py` | `Agent` | Shared base: DB access, run logging, lessons/good-news logging, company upsert. |
| `crm_app.py` | `CRMApp` | Optional UI/dashboard wiring for search, pipeline runs and exports. |

## Architecture

```
core.Agent (DB + logging)
        ▲
        │ inherited by
┌───────┼───────────────┬──────────────┬───────────────┐
│       │               │              │               │
CompanyFinder  ContactIntel  SocialScanner  Deduper   CRMQuery
                                   │
                            CEOAgent (orchestrator)
                                   │
                              CRMApp (UI)
```

All agents persist to a shared SQLite database (`CRM_DB`, default
`./crm_agents.db`).

## Tech Stack

- Python 3.11+
- Standard library + `sqlite3`
- Optional: web-search / LLM libraries for specific agents (declare in
  `requirements.txt` as needed)

## Installation

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # if present; core uses only stdlib
cp .env.example .env
```

## Environment Variables

See `.env.example` (all placeholders):

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Optional, for any LLM-assisted enrichment |
| `SERP_API_KEY` / `GOOGLE_API_KEY` / `SEARCH_ENGINE_ID` | Optional, for search-backed discovery |
| `CRM_DB` | SQLite database path |
| `CRM_DEBUG` | Verbose logging |

## Usage

```python
from agent_company_finder import CompanyFinder
from agent_contact_intel import ContactIntel

finder = CompanyFinder()
finder.find_and_save("coffee roaster", city="Casablanca", limit=20)

enricher = ContactIntel()
enricher.enrich_company(company_id=1)

# query / export
from agent_crm_query import CRMQuery
CRMQuery().export_csv("leads.csv")
```

Run the full pipeline:

```python
from agent_orchestrator import CEOAgent
CEOAgent().run_pipeline(niche="padel club")
```

## Security

- No credentials are committed. API keys are read from environment variables
  only (see `.env.example`).
- The local SQLite database is excluded from version control.
- Respect each source site's `robots.txt` and rate limits when scraping; this
  toolkit is intended for first-party lead research, not abusive harvesting.

## Status

This is an actively-used internal toolkit. Individual agents may depend on
optional third-party libraries (search/LLM providers) that you supply via
environment configuration; core data structures and the orchestration logic
are self-contained.

## License

MIT — see [LICENSE](LICENSE).

---

## Links

- 🌐 Website: [huggehub.com](https://www.huggehub.com)
- 💻 GitHub: [@astrodevit-creator](https://github.com/astrodevit-creator)
- 🔗 LinkedIn: _(add your profile URL)_
