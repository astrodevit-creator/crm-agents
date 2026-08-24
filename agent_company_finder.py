"""
Agent 1 — Company Finder
Searches the web for companies matching a keyword/industry/country,
creates CRM records from search results.
"""
import re
import json
import time
import socket
from urllib.parse import urlparse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from core import Agent, upsert_company, log_good_news, _now

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}

# Known false-positive / frustrating domains to skip
BLOCKED_TLD = re.compile(r"\.(xyz|top|click|download|gift|men|bet|loan|crypto|Rambler\.ru)$", re.I)
BLOCKED_DOMAIN = {
    "wikipedia", "google", "facebook", "twitter", "instagram", "linkedin", "tiktok",
    "youtube", "reddit", "quora", "pinterest", "amazon", "walmart", "ebay", "craigslist",
    "indeed", "glassdoor", "angellist", "producthunt", "medium", "news", "blogger",
    "wordpress", "tumblr", "shopify", "etsy", "aliexpress", "shop",
}


class CompanyFinder(Agent):
    def __init__(self):
        super().__init__("CompanyFinder")

    def search(self, keyword: str, country: str = "", industry: str = "",
               max_results: int = 30) -> list:
        """
        Find companies matching keyword (+ optional country/industry).
        Uses DuckDuckGo HTML search + direct website discovery.
        Returns list of dicts with name/domain/website/country/industry.
        """
        keyword = keyword.strip()
        results = []

        # 1) DuckDuckGo HTML search
        ddg_results = self._ddg_search(keyword, country, max_results)
        for r in ddg_results:
            if self._is_valid_company(r):
                results.append(r)

        # 2) If too few, try Google via requests (limited)
        if len(results) < 10:
            google_results = self._google_search(keyword, country, max_results)
            for r in google_results:
                if r not in results and self._is_valid_company(r):
                    results.append(r)

        # Deduplicate by domain
        seen = set()
        deduped = []
        for r in results:
            dom = r.get("domain", "").lower()
            if dom and dom not in seen:
                seen.add(dom)
                deduped.append(r)
            elif not dom and r["name"] not in seen:
                seen.add(r["name"])
                deduped.append(r)

        self.log("search_batch", detail=f"keyword={keyword!r} country={country!r} industry={industry!r} found={len(deduped)}",
                 result={"keyword": keyword, "country": country, "industry": industry,
                         "total_found": len(deduped), "results": deduped[:5]})
        return deduped[:max_results]

    def _ddg_search(self, keyword, country, max_results):
        """DuckDuckGo HTML search with multiple fallback strategies."""
        results = []

        # Strategy 1: ddg html (lite)
        r1 = self._ddg_html_search(keyword, country, max_results)
        results.extend(r1)

        # Strategy 2: Bing search (often works when ddg is blocked)
        if len(results) < max_results * 0.5:
            r2 = self._bing_search(keyword, country, max_results)
            for r in r2:
                if r not in results:
                    results.append(r)

        # Strategy 3: direct well-known domain guesses for common keywords
        if len(results) < 5:
            r3 = self._guess_domains(keyword, country)
            for r in r3:
                if r not in results:
                    results.append(r)

        # Trim to max
        return results[:max_results]

    def _ddg_html_search(self, keyword, country, max_results):
        results = []
        try:
            url = "https://html.duckduckgo.com/html/"
            params = {"q": keyword}
            if country:
                params["q"] += f" {country} company"
            resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return results
            soup = BeautifulSoup(resp.text, "html.parser")
            for result in soup.select(".result results_links results_links_deep"):
                link_el = result.select_one("a.result__a")
                title_el = result.select_one("a.result__a")
                snippet_el = result.select_one(".result__snippet")
                if not link_el:
                    continue
                url_val = link_el.get("href", "")
                # unwrap ddg redirect FIRST so we block real domains
                url_val = self._unwrap_ddg(url_val)
                if not url_val:
                    continue
                title = (title_el.get_text(strip=True) if title_el else "").strip()
                snippet = (snippet_el.get_text(strip=True) if snippet_el else "").strip()
                if not title:
                    continue
                domain = self._extract_domain(url_val)
                # block check AFTER we have the real domain
                if domain in BLOCKED_DOMAIN:
                    continue
                if BLOCKED_TLD.search(domain or ""):
                    continue
                results.append({
                    "name": title[:120],
                    "website": url_val if url_val.startswith("http") else f"https://{url_val}",
                    "domain": domain or "",
                    "country": country,
                    "source": "duckduckgo",
                    "source_url": url_val,
                    "snippet": snippet[:300],
                })
                if len(results) >= max_results:
                    break
        except Exception as e:
            self.log("ddg_error", detail=str(e))
        return results

    def _bing_search(self, keyword, country, max_results):
        """Bing search via requests — good fallback when DDG blocked."""
        results = []
        try:
            url = "https://www.bing.com/search"
            params = {"q": keyword, "count": str(min(max_results, 20))}
            if country:
                params["q"] += f" {country}"
            resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return results
            soup = BeautifulSoup(resp.text, "html.parser")
            for li in soup.select("li.b_algo"):
                h2 = li.select_one("h2")
                a = li.select_one("a")
                p = li.select_one(".b_caption p, .b_lineclamp")
                if not h2 or not a:
                    continue
                url_val = a.get("href", "")
                if not url_val or not url_val.startswith("http"):
                    continue
                title = h2.get_text(strip=True)
                snippet = (p.get_text(strip=True) if p else "").strip()
                domain = self._extract_domain(url_val)
                if domain in BLOCKED_DOMAIN:
                    continue
                if BLOCKED_TLD.search(domain or ""):
                    continue
                results.append({
                    "name": title[:120],
                    "website": url_val,
                    "domain": domain or "",
                    "country": country,
                    "source": "bing",
                    "source_url": url_val,
                    "snippet": snippet[:300],
                })
                if len(results) >= max_results:
                    break
        except Exception as e:
            self.log("bing_error", detail=str(e))
        return results

    def _guess_domains(self, keyword, country):
        """For common short keywords, try likely real domains."""
        results = []
        kw_clean = keyword.strip().lower()
        # only do this for short, specific keywords
        if len(kw_clean.split()) > 3:
            return results
        # common ccTLDs and .com for the country
        tlds = [".com"]
        if country:
            c = country.lower()
            if c in ("morocco", "ma"):
                tlds = [".com", ".ma", ".co.ma"]
            elif c in ("france", "fr"):
                tlds = [".com", ".fr", ".paris"]
            elif c in ("spain", "es"):
                tlds = [".com", ".es"]
            elif c in ("tunisia", "tn"):
                tlds = [".com", ".tn"]
            elif c in ("canada", "ca"):
                tlds = [".com", ".ca"]
            elif c in ("algeria", "dz"):
                tlds = [".com", ".dz"]
            elif c in ("egypt", "eg"):
                tlds = [".com", ".eg"]

        # Strip spaces/special chars from keyword for domain
        dom_base = re.sub(r"[^a-z0-9]", "", kw_clean)
        if len(dom_base) < 3:
            return results

        for tld in tlds:
            guess = f"{dom_base}{tld}"
            if guess in BLOCKED_DOMAIN:
                continue
            # quick probe: does the domain resolve?
            try:
                import socket as _sock
                _sock.create_connection((guess, 443), timeout=2).close()
                # If alive, add as a found company
                results.append({
                    "name": keyword.strip().title(),
                    "website": f"https://{guess}",
                    "domain": guess,
                    "country": country,
                    "source": "domain_guess",
                    "source_url": f"https://{guess}",
                    "snippet": f"Guessed domain for {keyword}",
                })
                if len(results) >= 3:
                    break
            except Exception:
                pass
        return results

    def _google_search(self, keyword, country, max_results):
        """Google search via requests (limited, may be blocked)."""
        results = []
        try:
            url = "https://www.google.com/search"
            params = {"q": keyword, "num": str(min(max_results, 10))}
            if country:
                params["q"] += f" {country}"
            resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return results
            soup = BeautifulSoup(resp.text, "html.parser")
            for div in soup.select("div.g, div.MjjYud, div[data-sokoban-container] a"):
                link_el = div.select_one("a")
                title_el = div.select_one("h3")
                if not link_el or not title_el:
                    continue
                url_val = link_el.get("href", "")
                if not url_val or not url_val.startswith("http"):
                    continue
                title = title_el.get_text(strip=True)
                if not title:
                    continue
                domain = self._extract_domain(url_val)
                if domain in BLOCKED_DOMAIN:
                    continue
                if BLOCKED_TLD.search(domain or ""):
                    continue
                results.append({
                    "name": title[:120],
                    "website": url_val,
                    "domain": domain or "",
                    "country": country,
                    "source": "google",
                    "source_url": url_val,
                    "snippet": "",
                })
                if len(results) >= max_results:
                    break
        except Exception as e:
            self.log("google_error", detail=str(e))
        return results

    def _unwrap_ddg(self, url):
        """Unwrap DuckDuckGo redirect URLs."""
        if not url:
            return ""
        m = re.search(r"uddg=([^&]+)", url)
        if m:
            from urllib.parse import unquote
            return unquote(m.group(1))
        return url if url.startswith("http") else ""

    def _extract_domain(self, url):
        try:
            # Unwrap Bing redirect URLs (bing.com/ck/a?...&u=a1<base64>)
            m = re.search(r"[?&]u=a1([A-Za-z0-9+/=]+)", url)
            if m:
                import base64
                try:
                    decoded = base64.b64decode(m.group(1) + "==").decode("utf-8", "ignore")
                    # bing prefixes with "a1" and the real URL follows
                    real = re.sub(r"^a1(aHR0c[^\s]*)", lambda mm: mm.group(1), decoded)
                    # the a1 prefix IS the base64 of "http" — strip it
                    if real.startswith("a1"):
                        real = base64.b64decode(real + "==").decode("utf-8", "ignore")
                    url = real
                except Exception:
                    pass

            p = urlparse(url)
            dom = p.netloc or p.path
            dom = dom.lower().strip("/")
            if dom.startswith("www."):
                dom = dom[4:]
            return dom
        except Exception:
            return ""

    def _is_valid_company(self, r):
        """Basic sanity: has a name and a plausible domain."""
        name = r.get("name", "").strip()
        domain = r.get("domain", "").strip()
        if not name or len(name) < 3:
            return False
        if len(name) < 5 and not domain:
            return False
        if domain and (domain.startswith("http") or len(domain) < 3):
            return False
        # Skip generic pages
        if any(x in name.lower() for x in ["login", "sign in", "signup", "register",
                                              "cart", "checkout", "my account", "search results"]):
            return False
        return True

    def find_and_save(self, keyword: str, country: str = "", industry: str = "",
                      max_results: int = 30) -> list:
        """Search + save companies to CRM. Returns saved company ids."""
        findings = self.search(keyword, country, industry, max_results)
        saved_ids = []
        for f in findings:
            cid = upsert_company(
                name=f["name"],
                website=f.get("website", ""),
                domain=f.get("domain", ""),
                country=f.get("country", "") or country,
                industry=industry,
                description=f.get("snippet", ""),
                source=f"search:{f.get('source','')}",
                source_url=f.get("source_url", ""),
                status="new",
            )
            if cid:
                saved_ids.append(cid)
                log_good_news("company_found", cid,
                              f"Found: {f['name']}  |  {f.get('website','')}")
        self.log("save_batch", detail=f"saved {len(saved_ids)} companies for keyword={keyword!r}",
                 result={"keyword": keyword, "saved_ids": saved_ids})
        return saved_ids


# ---------------------------------------------------------------------------
# Standalone CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    finder = CompanyFinder()
    keyword = sys.argv[1] if len(sys.argv) > 1 else "coffee shop"
    country = sys.argv[2] if len(sys.argv) > 2 else ""
    industry = sys.argv[3] if len(sys.argv) > 3 else ""
    max_r = int(sys.argv[4]) if len(sys.argv) > 4 else 20
    ids = finder.find_and_save(keyword, country, industry, max_r)
    print(f"Found & saved {len(ids)} companies:")
    for cid in ids:
        c = __import__("core").get_company(cid)
        print(f"  [{cid}] {c['name']}  |  {c['website']}  |  {c['country']}")
