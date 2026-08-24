"""
Agent 5 — Deduper
Finds and merges duplicate companies across the CRM.
"""
import re
from difflib import SequenceMatcher
from urllib.parse import urlparse

from core import Agent, get_company, set_company_field, log_lesson, _now

DUP_THRESHOLD_NAME = 0.85


class Deduper(Agent):
    def __init__(self):
        super().__init__("Deduper")

    def find_duplicates(self, batch_size: int = 200) -> list:
        import sqlite3 as _sqlite
        conn = _sqlite.connect(str(__import__("core").DB_PATH))
        conn.row_factory = _sqlite.Row
        duplicates = []
        try:
            rows = conn.execute(
                "SELECT id, name, domain, website, country, city FROM companies ORDER BY id"
            ).fetchall()
            companies = [dict(r) for r in rows]

            # Exact domain match
            domain_map = {}
            for c in companies:
                dom = (c.get("domain") or "").lower().strip()
                if dom:
                    domain_map.setdefault(dom, []).append(c["id"])

            for dom, ids in domain_map.items():
                if len(ids) > 1:
                    master = ids[0]
                    for dup_id in ids[1:]:
                        duplicates.append((master, dup_id, f"exact domain: {dom}"))

            # Similar names + same country/city
            for i in range(len(companies)):
                for j in range(i + 1, len(companies)):
                    ci = companies[i]
                    cj = companies[j]
                    if ci["id"] == cj["id"]:
                        continue
                    # Exact domain already handled
                    dom_i = (ci.get("domain") or "").lower().strip()
                    dom_j = (cj.get("domain") or "").lower().strip()
                    if dom_i and dom_j and dom_i != dom_j:
                        if dom_i.endswith("." + dom_j) or dom_j.endswith("." + dom_i):
                            master, dup_id = (ci["id"], cj["id"]) if dom_i.endswith("." + dom_j) else (cj["id"], ci["id"])
                            if (master, dup_id, "subdomain") not in duplicates:
                                duplicates.append((master, dup_id, "subdomain"))
                        continue
                    # Name similarity + same country/city
                    name_i = (ci.get("name") or "").strip().lower()
                    name_j = (cj.get("name") or "").strip().lower()
                    if not name_i or not name_j:
                        continue
                    sim = SequenceMatcher(None, name_i, name_j).ratio()
                    if sim >= DUP_THRESHOLD_NAME:
                        country_match = (ci.get("country") or "") == (cj.get("country") or "")
                        city_match = (ci.get("city") or "") == (cj.get("city") or "")
                        if country_match or city_match:
                            master, dup_id = (ci["id"], cj["id"]) if sim >= 0.92 else (ci["id"], cj["id"])
                            reason = f"name similarity {sim:.2f} (country={country_match}, city={city_match})"
                            duplicates.append((master, dup_id, reason))
        finally:
            conn.close()

        self.log("find_duplicates", detail=f"scanned {len(companies)} companies, found {len(duplicates)} dup pairs",
                 result={"total_companies": len(companies), "duplicates": len(duplicates)})
        return duplicates

    def merge(self, master_id: int, dup_id: int, reason: str = "") -> bool:
        master = get_company(master_id)
        dup = get_company(dup_id)
        if not master or not dup:
            return False
        if dup_id == master_id:
            return False

        fields = [
            "decision_maker", "dm_title", "dm_email", "dm_phone",
            "email", "email_source",
            "phone", "phone_source",
            "whatsapp", "instagram", "tiktok", "facebook", "linkedin", "twitter", "youtube",
        ]
        updated = []
        for f in fields:
            mv = master.get(f)
            dv = dup.get(f)
            if not mv and dv:
                set_company_field(master_id, **{f: dv})
                updated.append(f)

        master_notes = (master.get("notes") or "").strip()
        dup_notes = (dup.get("notes") or "").strip()
        if dup_notes and dup_notes not in master_notes:
            new_notes = (master_notes + (" | " if master_notes else "") + f"[MERGED from #{dup_id}] {dup_notes}").strip()
            set_company_field(master_id, notes=new_notes)

        set_company_field(dup_id, duplicate_of=master_id, status="merged")

        log_lesson(f"Merged #{dup_id} into #{master_id}: {reason or 'contact consolidation'}",
                   0.0, 1.0, f"Keep #{master_id} as master")

        self.log("merge", target=str(master_id),
                 detail=f"dup={dup_id} reason={reason!r} fields_updated={updated}",
                 result={"master": master_id, "dup": dup_id, "fields_updated": updated})
        return True

    def dedupe_batch(self, batch_size: int = 200) -> dict:
        dup_pairs = self.find_duplicates(batch_size)
        merged = 0
        skipped = 0
        for master_id, dup_id, reason in dup_pairs:
            try:
                if self.merge(master_id, dup_id, reason):
                    merged += 1
                else:
                    skipped += 1
            except Exception as e:
                self.log("merge_error", target=str(dup_id), detail=str(e))
                skipped += 1
        self.log("dedupe_batch", detail=f"pairs={len(dup_pairs)} merged={merged} skipped={skipped}",
                 result={"pairs": len(dup_pairs), "merged": merged, "skipped": skipped})
        return {"pairs": len(dup_pairs), "merged": merged, "skipped": skipped}


if __name__ == "__main__":
    deduper = Deduper()
    s = deduper.dedupe_batch()
    print("Dedupe result:", s)
