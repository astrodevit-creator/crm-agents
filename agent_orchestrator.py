"""
Agent 0 — CEO Orchestrator
Coordinates all sub-agents into a full discovery pipeline.
"""
import time
import threading
from typing import Optional, List

from core import Agent, get_stats, log_good_news
from agent_company_finder import CompanyFinder
from agent_contact_intel import ContactIntel, enrich_batch
from agent_social_scanner import SocialScanner, scan_batch
from agent_deduper import Deduper
from agent_crm_query import CRMQuery


class CEOAgent(Agent):
    def __init__(self):
        super().__init__("CEO")
        self.finder = CompanyFinder()
        self.intel = ContactIntel()
        self.social = SocialScanner()
        self.dedup = Deduper()
        self.query = CRMQuery()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def run_pipeline(self, keyword: str, country: str = "", industry: str = "",
                     max_find: int = 30) -> dict:
        self.log("pipeline_start", detail=f"keyword={keyword!r} country={country!r} industry={industry!r}",
                 result={"keyword": keyword, "country": country, "industry": industry})

        found_ids = self.finder.find_and_save(keyword, country, industry, max_find)
        if not found_ids:
            return {"status": "empty", "message": f"No companies found for {keyword!r}"}

        intermediate = {"found": len(found_ids), "company_ids": found_ids}

        enrich_result = enrich_batch(found_ids, self.intel)
        intermediate["enrichment"] = enrich_result

        social_result = scan_batch(found_ids, self.social)
        intermediate["social"] = social_result

        dedupe_result = self.dedup.dedupe_batch()
        intermediate["dedupe"] = dedupe_result

        stats = get_stats()
        intermediate["stats"] = stats

        high_opp = [cid for cid in found_ids
                     if __import__("core").get_company(cid)["opportunity_score"] >= 70]
        intermediate["high_opportunity"] = len(high_opp)

        self.log("pipeline_done", detail=f"keyword={keyword!r} total_found={len(found_ids)}",
                 result=intermediate)

        good_msg = (
            f"Pipeline done for {keyword!r}: "
            f"found {len(found_ids)} companies, "
            f"{enrich_result['emails']} emails, "
            f"{enrich_result['phones']} phones, "
            f"{enrich_result['whatsapp']} WhatsApp, "
            f"{enrich_result['social']} social profiles"
        )
        log_good_news("pipeline_complete", None, good_msg)
        return intermediate

    def start_loop(self, keywords: List[str], country: str = "",
                   industry: str = "", interval_sec: int = 300,
                   max_per_cycle: int = 10):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop_body, args=(keywords, country, industry, interval_sec, max_per_cycle),
            daemon=True, name="CEO-LOOP"
        )
        self._thread.start()
        self.log("loop_started", detail=f"keywords={keywords} interval={interval_sec}s",
                 result={"keywords": keywords, "interval": interval_sec})
        return self._thread

    def stop_loop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None
        self._running = False
        self.log("loop_stopped")

    def _loop_body(self, keywords, country, industry, interval, max_per):
        while self._running:
            for kw in keywords:
                if not self._running:
                    return
                try:
                    self.run_pipeline(kw, country, industry, max_per)
                except Exception as e:
                    self.log("loop_error", detail=f"keyword={kw!r}: {e}")
                if not self._running:
                    return
                time.sleep(5)
            if self._running:
                time.sleep(interval)

    def get_dashboard(self) -> dict:
        stats = get_stats()
        import sqlite3
        conn = sqlite3.connect(str(__import__("core").DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM agent_runs ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
            runs = [dict(r) for r in rows]
        finally:
            conn.close()
        return {
            "stats": stats,
            "recent_runs": runs,
        }


if __name__ == "__main__":
    import sys, json
    ceo = CEOAgent()
    if len(sys.argv) < 2:
        print("Usage: python agent_orchestrator.py <keyword> [country] [industry] [max_find]")
        print("   or: python agent_orchestrator.py loop <keyword1>,<keyword2>... [interval_sec]")
        sys.exit(1)

    if sys.argv[1].lower() == "loop":
        kw_str = sys.argv[2] if len(sys.argv) > 2 else "coffee shop,restaurant"
        keywords = [k.strip() for k in kw_str.split(",")]
        interval = int(sys.argv[3]) if len(sys.argv) > 3 else 300
        country = sys.argv[4] if len(sys.argv) > 4 else ""
        industry = sys.argv[5] if len(sys.argv) > 5 else ""
        thread = ceo.start_loop(keywords, country, industry, interval, max_per_cycle=5)
        print(f"Loop started: keywords={keywords} interval={interval}s  (thread={thread.name})")
        print("Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(10)
                stats = get_stats()
                print(f"\rStats: {stats['total_companies']} companies, "
                      f"{stats['with_email']} emails, {stats['with_phone']} phones, "
                      f"{stats['with_whatsapp']} WhatsApp, {stats['with_instagram']} IG, "
                      f"{stats['with_tiktok']} TikTok, {stats['with_facebook']} FB, "
                      f"{stats['with_linkedin']} LinkedIn",
                      end="", flush=True)
        except KeyboardInterrupt:
            ceo.stop_loop()
            print("\nLoop stopped.")
    else:
        keyword = sys.argv[1]
        country = sys.argv[2] if len(sys.argv) > 2 else ""
        industry = sys.argv[3] if len(sys.argv) > 3 else ""
        max_find = int(sys.argv[4]) if len(sys.argv) > 4 else 20
        result = ceo.run_pipeline(keyword, country, industry, max_find)
        print("\n=== Pipeline Result ===")
        print(json.dumps(result, indent=2, default=str))
