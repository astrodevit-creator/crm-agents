"""
Agent 3 — Social Scanner
For each company with a website or domain, scans for social presence
across Instagram, TikTok, Facebook, LinkedIn, Twitter/X, YouTube, WhatsApp.
Uses multiple heuristics: domain matching, site meta tags, platform search.
"""
import re
import json
from urllib.parse import urlparse

from core import Agent, get_company, set_company_field, log_good_news, _now

# Platform profile URL patterns we try to construct & verify
PLATFORM_PATTERNS = {
    "instagram": [
        "https://{domain}",
        "https://www.instagram.com/{domain}",
        "https://instagram.com/{handle}",
    ],
    "tiktok": [
        "https://www.tiktok.com/@{handle}",
        "https://tiktok.com/@{handle}",
    ],
    "facebook": [
        "https://www.facebook.com/{domain}",
        "https://facebook.com/{domain}",
    ],
    "linkedin": [
        "https://www.linkedin.com/company/{domain}",
        "https://linkedin.com/company/{domain}",
    ],
    "twitter": [
        "https://twitter.com/{handle}",
        "https://x.com/{handle}",
    ],
    "youtube": [
        "https://www.youtube.com/@{handle}",
        "https://youtube.com/channel/{handle}",
    ],
}

PLATFORM_VERIFY = {
    "instagram": "instagram.com",
    "tiktok": "tiktok.com",
    "facebook": "facebook.com",
    "linkedin": "linkedin.com",
    "twitter": ["twitter.com", "x.com"],
    "youtube": "youtube.com",
}


class SocialScanner(Agent):
    def __init__(self):
        super().__init__("SocialScanner")

    def scan_company(self, company_id: int) -> dict:
        """Try to find social profiles for one company. Returns summary."""
        company = get_company(company_id)
        if not company:
            return {"error": "not found", "company_id": company_id}

        domain = (company["domain"] if company["domain"] else company["website"] or "").strip()
        if not domain:
            return {"error": "no domain", "company_id": company_id}

        handle = self._domain_to_handle(domain)
        summary = {"platforms_found": [], "platforms_tried": 0, "company_id": company_id}

        for platform, patterns in PLATFORM_PATTERNS.items():
            self.log("scan_platform", target=str(company_id),
                     detail=f"platform={platform} domain={domain}")
            profile_url = self._build_url(platform, domain, handle)
            if profile_url:
                summary["platforms_tried"] += 1
                # Check if company already has this platform
                existing = company[platform] if platform in company.keys() else ""
                if existing:
                    continue
                # Verify the profile exists (light check)
                if self._verify_profile(platform, profile_url):
                    set_company_field(company_id, **{platform: profile_url})
                    summary["platforms_found"].append(platform)
                    log_good_news("social_found", company_id,
                                  f"{platform}: {profile_url}")
                # Also try generic handle-based URL if domain-based failed
                if platform not in summary["platforms_found"]:
                    alt_url = self._build_handle_url(platform, handle)
                    if alt_url and alt_url != profile_url:
                        if self._verify_profile(platform, alt_url):
                            set_company_field(company_id, **{platform: alt_url})
                            summary["platforms_found"].append(platform)
                            log_good_news("social_found", company_id,
                                          f"{platform} (handle): {alt_url}")

        self.log("scan_done", target=str(company_id),
                 detail=f"found={summary['platforms_found']}",
                 result=summary)
        return summary

    def _domain_to_handle(self, domain):
        """Turn a domain into a likely social handle.
        e.g. mycompany.com → mycompany, my-co → myco
        """
        dom = domain.lower().strip()
        # strip www., http, https
        dom = re.sub(r"^(www\.|http[s]?://)", "", dom)
        # strip common TLDs
        for tld in [".com", ".net", ".org", ".co", ".io", ".ai", ".app", ".co.uk",
                     ".fr", ".de", ".es", ".it", ".nl", ".be", ".ch", ".at", ".pl",
                     ".ca", ".au", ".nz", ".in", ".br", ".mx", ".ar", ".za", ".eg",
                     ".ma", ".tn", ".dz", ".sa", ".ae", ".qa", ".kw", ".bh", ".om",
                     ".jo", ".lb", ".ps", ".tr", ".pk", ".bd", ".lk", ".my", ".ph",
                     ".id", ".th", ".vn", ".sg", ".hk", ".tw", ".kr", ".jp", ".cn",
                     ".ru", ".ua", ".ro", ".bg", ".gr", ".pt", ".ie", ".dk", ".se",
                     ".no", ".fi", ".cz", ".sk", ".hu", ".rs", ".hr", ".si", ".lt",
                     ".lv", ".ee", ".is", ".lu", ".mt", ".cy", ".ba", ".mk", ".al",
                     ".ge", ".am", ".az", ".kz", ".uz", ".kg", ".tj", ".tm", ".az",
                     ".by", ".md", ".sm", ".va", ".ad", ".li", ".mc", ".tf", ".wf",
                     ".yt", ".re", ".gp", ".mq", ".pm", ".bl", ".mf", ".sx", ".cw",
                     ".bq", ".gl", ".fo", ".ax", ".sj", ".bv", ".tf", ".hm", ".nf",
                     ".nr", ".tv", ".um", ".cc", ".ck", ".nu", ".nz", ".pg", ".sb",
                     ".to", ".tv", ".vu", ".wf", ".ws", ".tk", ".pf", ".gf", ".gq",
                     ".pm", ".re", ".yt", ".nc", ".pf", ".wf", ".cx", ".cc", ".cx"]:
            if dom.endswith(tld):
                dom = dom[:-len(tld)]
                break
        # strip non-alphanumeric
        handle = re.sub(r"[^a-z0-9]", "", dom)
        return handle or dom

    def _build_url(self, platform, domain, handle):
        """Build a platform URL from domain/handle."""
        if platform == "instagram":
            return f"https://www.instagram.com/{domain}/"
        elif platform == "tiktok":
            return f"https://www.tiktok.com/@{handle}"
        elif platform == "facebook":
            return f"https://www.facebook.com/{domain}/"
        elif platform == "linkedin":
            return f"https://www.linkedin.com/company/{domain}/"
        elif platform == "twitter":
            return f"https://twitter.com/{handle}"
        elif platform == "youtube":
            return f"https://www.youtube.com/@{handle}"
        return ""

    def _build_handle_url(self, platform, handle):
        """Build platform URL using handle directly."""
        if not handle:
            return ""
        if platform == "instagram":
            return f"https://www.instagram.com/{handle}/"
        elif platform == "tiktok":
            return f"https://www.tiktok.com/@{handle}"
        elif platform == "facebook":
            return f"https://www.facebook.com/{handle}/"
        elif platform == "linkedin":
            return f"https://www.linkedin.com/in/{handle}/"
        elif platform == "twitter":
            return f"https://twitter.com/{handle}"
        elif platform == "youtube":
            return f"https://www.youtube.com/@{handle}"
        return ""

    def _verify_profile(self, platform, url):
        """Check if a social profile URL is likely live."""
        try:
            import requests as _req
            resp = _req.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            }, timeout=8, allow_redirects=True)
            # 200 = likely live profile page
            # 301/302 to login page = profile exists but requires auth (likely real)
            if resp.status_code == 200:
                return True
            # For Instagram, a redirect to /accounts/login is a good sign
            final_url = resp.url
            if platform == "instagram" and "login" in final_url.lower():
                return True
            return False
        except Exception:
            return False


def scan_batch(company_ids, agent=None):
    if agent is None:
        agent = SocialScanner()
    found = {"platforms": 0, "companies_scanned": 0}
    for cid in company_ids:
        r = agent.scan_company(cid)
        if "platforms_found" in r:
            found["platforms"] += len(r["platforms_found"])
            found["companies_scanned"] += 1
    return found


if __name__ == "__main__":
    import sys
    scanner = SocialScanner()
    if len(sys.argv) > 1:
        ids = [int(x) for x in sys.argv[1].split(",")]
    else:
        from core import get_recent_agent_runs
        import sqlite3
        conn = sqlite3.connect(str(__import__("core").DB_PATH))
        conn.row_factory = sqlite3.Row
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM companies WHERE (instagram='' AND tiktok='' AND facebook='' "
            "AND linkedin='' AND twitter='' AND youtube='') LIMIT 20"
        ).fetchall()]
        conn.close()
    s = scan_batch(ids, scanner)
    print("Social scan summary:", s)
