"""
Agent 4 — CRM Query
Full-text search, filter, sort, and export companies from the CRM.
Supports CSV, Excel, and JSON export.
"""
import json
import csv
from io import StringIO
from pathlib import Path
from datetime import datetime
from typing import Optional

from core import Agent, search_companies, get_company, get_contacts, get_stats, mark_company_exported, _now

XLSX_AVAILABLE = False
try:
    import openpyxl
    XLSX_AVAILABLE = True
except ImportError:
    pass


class CRMQuery(Agent):
    def __init__(self):
        super().__init__("CRMQuery")

    def search(self, query: str, limit: int = 50, offset: int = 0,
               filters: dict = None) -> list:
        if not query or not query.strip():
            filters = filters or {}
            filters["_all"] = True
            return self._list_all(limit, offset, filters)

        rows = search_companies(query.strip(), limit, offset, filters)
        result = [dict(r) for r in rows]
        self.log("search", detail=f"query={query!r} limit={limit} filters={filters or {}}",
                 result={"query": query, "total": len(result), "results": result[:3]})
        return result

    def _list_all(self, limit, offset, filters):
        import sqlite3 as _sqlite
        conn = _sqlite.connect(str(__import__("core").DB_PATH))
        conn.row_factory = _sqlite.Row
        try:
            base = "SELECT * FROM companies WHERE 1=1"
            params = []
            f = filters or {}
            if f.get("country"):
                base += " AND country = ?"
                params.append(f["country"])
            if f.get("industry"):
                base += " AND industry = ?"
                params.append(f["industry"])
            if f.get("status"):
                base += " AND status = ?"
                params.append(f["status"])
            if f.get("min_score"):
                base += " AND opportunity_score >= ?"
                params.append(f["min_score"])
            if f.get("has_email"):
                base += " AND email != ''"
            if f.get("has_phone"):
                base += " AND phone != ''"
            if f.get("has_whatsapp"):
                base += " AND whatsapp != ''"
            if f.get("has_social"):
                base += " AND (instagram != '' OR tiktok != '' OR facebook != '' OR linkedin != '')"
            base += " ORDER BY opportunity_score DESC, updated_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            rows = conn.execute(base, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_company_full(self, company_id: int) -> dict:
        company = get_company(company_id)
        if not company:
            return {}
        contacts = get_contacts(company_id)
        return {
            "company": dict(company),
            "contacts": [dict(c) for c in contacts],
        }

    def export_csv(self, company_ids: list = None, query: str = None,
                   filters: dict = None, path: str = None) -> str:
        if company_ids:
            companies = [get_company(cid) for cid in company_ids if get_company(cid)]
        elif query:
            companies = search_companies(query, 10000, 0, filters)
        else:
            import sqlite3
            conn = sqlite3.connect(str(__import__("core").DB_PATH))
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM companies ORDER BY opportunity_score DESC").fetchall()
            conn.close()
            companies = [dict(r) for r in rows]

        if not companies:
            return ""

        fname = path or f"crm_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        fields = [
            "id", "name", "domain", "website", "country", "city", "industry",
            "description", "est_size", "founded_year", "revenue_range",
            "employees_min", "employees_max",
            "decision_maker", "dm_title", "dm_email", "dm_phone",
            "email", "email_source", "phone", "phone_source",
            "whatsapp", "instagram", "tiktok", "facebook", "linkedin", "twitter", "youtube",
            "other_social", "primary_contact", "contact_confidence",
            "source", "source_url", "opportunity_score", "best_service",
            "status", "notes", "created_at", "updated_at",
        ]

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for c in companies:
            c = dict(c) if hasattr(c, "keys") else c
            writer.writerow({f: c[f] if f in c else "" for f in fields})
        csv_text = output.getvalue()

        out_path = Path(fname)
        if not out_path.is_absolute():
            out_path = Path.home() / out_path
        out_path.write_text(csv_text, encoding="utf-8")
        self.log("export_csv", detail=f"exported {len(companies)} companies to {out_path}",
                 result={"path": str(out_path), "count": len(companies)})
        return str(out_path)

    def export_xlsx(self, company_ids: list = None, query: str = None,
                    filters: dict = None, path: str = None) -> Optional[str]:
        if not XLSX_AVAILABLE:
            return None

        if company_ids:
            companies = [get_company(cid) for cid in company_ids if get_company(cid)]
        elif query:
            companies = search_companies(query, 10000, 0, filters)
        else:
            import sqlite3
            conn = sqlite3.connect(str(__import__("core").DB_PATH))
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM companies ORDER BY opportunity_score DESC").fetchall()
            conn.close()
            companies = [dict(r) for r in rows]

        if not companies:
            return None

        fname = path or f"crm_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        out_path = Path(fname)
        if not out_path.is_absolute():
            out_path = Path.home() / out_path

        fields = [
            "id", "name", "domain", "website", "country", "city", "industry",
            "description", "est_size", "founded_year", "revenue_range",
            "employees_min", "employees_max",
            "decision_maker", "dm_title", "dm_email", "dm_phone",
            "email", "email_source", "phone", "phone_source",
            "whatsapp", "instagram", "tiktok", "facebook", "linkedin", "twitter", "youtube",
            "other_social", "primary_contact", "contact_confidence",
            "source", "source_url", "opportunity_score", "best_service",
            "status", "notes", "created_at", "updated_at",
        ]

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Companies"
        ws.append(fields)
        for c in companies:
            c = dict(c) if hasattr(c, "keys") else c
            row = []
            for f in fields:
                val = c[f] if f in c.keys() else ""
                if isinstance(val, str):
                    val = val[:255]
                row.append(val)
            ws.append(row)
        for col_idx, f in enumerate(fields, 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = min(max(len(f) + 4, 12), 40)

        wb.save(str(out_path))
        self.log("export_xlsx", detail=f"exported {len(companies)} companies to {out_path}",
                 result={"path": str(out_path), "count": len(companies)})
        return str(out_path)

    def export_json(self, company_ids: list = None, query: str = None,
                    filters: dict = None, path: str = None) -> Optional[str]:
        if company_ids:
            companies = [get_company(cid) for cid in company_ids if get_company(cid)]
        elif query:
            companies = search_companies(query, 10000, 0, filters)
        else:
            companies = [dict(r) for r in search_companies("", 10000, 0)]

        if not companies:
            return None

        clean = []
        for c in companies:
            if hasattr(c, "keys"):
                clean.append(dict(c))
            else:
                clean.append(c)

        fname = path or f"crm_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        out_path = Path(fname)
        if not out_path.is_absolute():
            out_path = Path.home() / out_path

        out_path.write_text(json.dumps(clean, indent=2, default=str), encoding="utf-8")
        self.log("export_json", detail=f"exported {len(clean)} companies to {out_path}",
                 result={"path": str(out_path), "count": len(clean)})
        return str(out_path)


if __name__ == "__main__":
    import sys
    crm = CRMQuery()
    if len(sys.argv) < 2:
        print("Usage: python agent_crm_query.py <search_query> [limit]")
        print("   or: python agent_crm_query.py export [csv|xlsx|json] [query]")
        sys.exit(1)
    cmd = sys.argv[1].lower()
    if cmd == "export":
        fmt = sys.argv[2] if len(sys.argv) > 2 else "csv"
        q = sys.argv[3] if len(sys.argv) > 3 else ""
        if fmt == "csv":
            print("CSV:", crm.export_csv(query=q))
        elif fmt == "xlsx":
            print("XLSX:", crm.export_xlsx(query=q))
        elif fmt == "json":
            print("JSON:", crm.export_json(query=q))
    else:
        q = " ".join(sys.argv[1:])
        results = crm.search(q)
        print(f"\nFound {len(results)} companies:\n")
        for i, c in enumerate(results, 1):
            print(f"{i}. [{c.get('opportunity_score',0):>3}] {c['name']}")
            print(f"   {c.get('website','')}  |  {c.get('country','')}  |  {c.get('industry','')}")
            print(f"   Email: {c.get('email','—'):<35} WhatsApp: {c.get('whatsapp','—')}")
            print(f"   IG: {c.get('instagram','—'):<40} TikTok: {c.get('tiktok','—')}")
            print(f"   FB: {c.get('facebook','—'):<40} LinkedIn: {c.get('linkedin','—')}")
            print()
