"""
Agent 2 — Contact Intel
Visits each company website and extracts:
  - email addresses
  - phone numbers
  - WhatsApp numbers
  - social media links (Instagram, TikTok, Facebook, LinkedIn, Twitter, YouTube)
Then validates and stores into CRM.
"""
import re
import json
import socket
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from core import Agent, get_company, set_company_field, add_contact, log_good_news, _now

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(
    r"(?:(?:\+|00)\d{1,3}[\s\-]?)?"
    r"(?:\(?\d{1,4}\)?[\s\-]?)"
    r"\d{3,14}"
    r"(?:[\s\-]?(?:ext|ext\.|x|extension)[\s\-]?\d{1,5})?"
)
SOCIAL_DOMAINS = {
    "instagram": ["instagram.com", "instagram"],
    "tiktok": ["tiktok.com", "tiktok"],
    "facebook": ["facebook.com", "fb.com", "m.facebook.com"],
    "linkedin": ["linkedin.com", "lnkd.in"],
    "twitter": ["twitter.com", "x.com", "t.co"],
    "youtube": ["youtube.com", "youtu.be"],
    "whatsapp": ["whatsapp.com", "wa.me", "api.whatsapp.com"],
    "telegram": ["t.me", "telegram.me"],
}
BANNED_EMAIL_DOMAINS = {"example.com", "test.com", "localhost", "sentry.wixpress.com",
                        "sentry-next.wixpress.com", "mailinator.com", "guerrillamail.com",
                        "tempmail.com", "10minutemail.com"}


class ContactIntel(Agent):
    def __init__(self):
        super().__init__("ContactIntel")

    def enrich_company(self, company_id: int) -> dict:
        """
        Visit a company website, scrape all contacts, update CRM.
        Returns summary dict.
        """
        company = get_company(company_id)
        if not company:
            return {"error": "company not found"}

        website = (company["website"] or company.get("domain", "")).strip()
        if not website:
            return {"error": "no website", "company_id": company_id}

        if not website.startswith("http"):
            website = f"https://{website}"

        # quick dead-host check
        host = urlparse(website).netloc
        if host and not self._host_alive(host):
            return {"error": f"host {host} unreachable", "company_id": company_id}

        self.log("start_enrich", target=str(company_id),
                 detail=f"website={website}")

        try:
            html = self._fetch(website)
        except Exception as e:
            self.log("fetch_error", target=str(company_id), detail=str(e))
            return {"error": str(e), "company_id": company_id}

        if not html:
            return {"error": "empty response", "company_id": company_id}

        summary = self._scan(html, website, company_id)
        self.log("enriched", target=str(company_id),
                 detail=f"emails={summary['emails']} phones={summary['phones']} "
                        f"whatsapp={summary['whatsapp']} social={summary['social_count']}",
                 result=summary)
        return summary

    def _host_alive(self, host, timeout=3):
        try:
            socket.create_connection((host, 443), timeout=timeout).close()
            return True
        except Exception:
            try:
                socket.create_connection((host, 80), timeout=timeout).close()
                return True
            except Exception:
                return False

    def _fetch(self, url, timeout=20):
        """Fetch HTML with retries."""
        for attempt in range(3):
            try:
                resp = requests.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                }, timeout=timeout, allow_redirects=True)
                if resp.status_code == 200:
                    return resp.text
                elif resp.status_code in (403, 429):
                    time.sleep(2 * (attempt + 1))
                else:
                    return ""
            except Exception:
                if attempt < 2:
                    time.sleep(2)
        return ""

    def _scan(self, html, base_url, company_id):
        """Parse HTML, extract all contacts, update CRM, return summary."""
        soup = BeautifulSoup(html, "html.parser")
        summary = {
            "emails": [], "phones": [], "whatsapp": [],
            "social": {}, "social_count": 0,
            "company_id": company_id,
        }

        # --- resolve all links to absolute ---
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True).lower()
            abs_url = urljoin(base_url, href)

            # 1) email via mailto:
            if href.startswith("mailto:"):
                email = href[7:].split("?")[0].strip()
                if self._valid_email(email):
                    self._add_email(company_id, email, f"mailto link: {text or href}", 0.9)
                    summary["emails"].append(email)

            # 2) phone via tel:
            if href.startswith("tel:"):
                phone = href[4:].strip()
                if self._valid_phone(phone):
                    self._add_phone(company_id, phone, f"tel link: {text or href}", 0.9)
                    summary["phones"].append(phone)

            # 3) WhatsApp
            if "whatsapp" in abs_url.lower() or "wa.me" in abs_url.lower():
                wa = self._extract_whatsapp_phone(abs_url)
                if wa:
                    self._add_whatsapp(company_id, wa, f"whatsapp link", 0.85)
                    summary["whatsapp"].append(wa)

            # 4) social media links
            dom = urlparse(abs_url).netloc.lower()
            for platform, domains in SOCIAL_DOMAINS.items():
                if platform == "whatsapp":
                    continue  # handled above
                for d in domains:
                    if d in dom:
                        if platform not in summary["social"]:
                            summary["social"][platform] = []
                        if abs_url not in summary["social"][platform]:
                            summary["social"][platform].append(abs_url)
                            # store on company
                            set_company_field(company_id, **{platform: abs_url})
                            log_good_news("social_found", company_id,
                                          f"{platform}: {abs_url}")
                            summary["social_count"] += 1
                        break

        # --- scan visible text for hidden emails/phones ---
        text = soup.get_text(" ", strip=True)

        # Emails in text
        for em in EMAIL_RE.findall(text):
            em = em.strip()
            if self._valid_email(em):
                self._add_email(company_id, em, "visible text", 0.6)
                if em not in summary["emails"]:
                    summary["emails"].append(em)

        # Phones in text (more aggressive — scan each line)
        for line in text.split("\n"):
            line = line.strip()
            if len(line) > 60:
                continue
            for ph in PHONE_RE.findall(line):
                ph = ph.strip()
                if self._valid_phone(ph):
                    self._add_phone(company_id, ph, "visible text", 0.5)
                    if ph not in summary["phones"]:
                        summary["phones"].append(ph)

        # Also check common subpages (contact, about, team)
        subpages = self._discover_subpages(soup, base_url)
        for sub in subpages[:5]:
            try:
                sub_html = self._fetch(sub, timeout=10)
                if sub_html:
                    sub_summary = self._scan(sub_html, sub, company_id)
                    for k in ("emails", "phones", "whatsapp"):
                        summary[k].extend(sub_summary[k])
                    for plat, urls in sub_summary["social"].items():
                        if plat not in summary["social"]:
                            summary["social"][plat] = []
                        for u in urls:
                            if u not in summary["social"][plat]:
                                summary["social"][plat].append(u)
                                set_company_field(company_id, **{plat: u})
                                summary["social_count"] += 1
            except Exception:
                pass

        summary["emails"] = list(dict.fromkeys(summary["emails"]))
        summary["phones"] = list(dict.fromkeys(summary["phones"]))
        summary["whatsapp"] = list(dict.fromkeys(summary["whatsapp"]))

        # Update company's social fields from summary
        for platform, urls in summary["social"].items():
            if urls and not get_company(company_id)[platform]:
                set_company_field(company_id, **{platform: urls[0]})

        return summary

    def _discover_subpages(self, soup, base_url):
        """Find likely contact/about subpages from nav links."""
        pages = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True).lower()
            if any(k in text for k in ["contact", "about", "team", "staff", "career",
                                         "support", "help", "reach"]):
                abs_url = urljoin(base_url, href)
                if abs_url.startswith(base_url) and abs_url != base_url:
                    pages.add(abs_url)
        return list(pages)

    def _valid_email(self, email):
        email = email.strip().lower()
        if not EMAIL_RE.fullmatch(email):
            return False
        local, _, dom = email.partition("@")
        if dom.lower() in BANNED_EMAIL_DOMAINS:
            return False
        # reject hash-looking local parts
        if re.fullmatch(r"[0-9a-f]{16,}", local):
            return False
        if len(local) < 2 or len(dom) < 4:
            return False
        return True

    def _valid_phone(self, phone):
        """Strict phone validation (scrub noise)."""
        cleaned = re.sub(r"[\s\-().]", "", phone)
        if not cleaned:
            return False
        # must have at least 7 digits, at most 15
        digits = re.sub(r"\D", "", cleaned)
        if len(digits) < 7 or len(digits) > 15:
            return False
        # reject masked digits
        if "*" in phone:
            return False
        # reject embedded 4-digit years
        if re.search(r"(19|20)\d{2}", phone):
            return False
        # reject repeated digit spam
        if len(set(digits)) < 3:
            return False
        # accept if starts with + or has a sane local prefix
        if cleaned.startswith("+") or cleaned.startswith("00"):
            return True
        if re.match(r"^0\d", cleaned):
            return True
        # international: at least 8 digits starting with country code
        if len(digits) >= 8 and digits[0] != "0":
            return True
        return False

    def _extract_whatsapp_phone(self, url):
        """Extract phone number from wa.me/ or api.whatsapp.com URL."""
        m = re.search(r"(?:wa\.me/|api\.whatsapp\.com/send\?phone=)(\d+)", url)
        if m:
            digits = m.group(1)
            if len(digits) >= 7:
                return f"+{digits}"
        return ""

    def _add_email(self, company_id, email, source, confidence):
        email = email.strip().lower()
        c = get_company(company_id)
        if c and c["email"] == email:
            return
        add_contact(company_id, "email", email, source, confidence)
        if not c or not c["email"]:
            set_company_field(company_id, email=email, email_source=source,
                              contact_confidence=max(c["contact_confidence"] if c else 0, confidence))
            log_good_news("email_found", company_id, f"Email: {email}")
        # Also set as dm_email if looks personal
        if self._looks_personal(email):
            set_company_field(company_id, dm_email=email)

    def _add_phone(self, company_id, phone, source, confidence):
        phone = phone.strip()
        c = get_company(company_id)
        if c and c["phone"] == phone:
            return
        add_contact(company_id, "phone", phone, source, confidence)
        if not c or not c["phone"]:
            set_company_field(company_id, phone=phone, phone_source=source,
                              contact_confidence=max(c["contact_confidence"] if c else 0, confidence))
            log_good_news("phone_found", company_id, f"Phone: {phone}")

    def _add_whatsapp(self, company_id, wa_number, source, confidence):
        if not wa_number:
            return
        c = get_company(company_id)
        if c and c["whatsapp"] == wa_number:
            return
        add_contact(company_id, "whatsapp", wa_number, source, confidence)
        if not c or not c["whatsapp"]:
            set_company_field(company_id, whatsapp=wa_number,
                              contact_confidence=max(c["contact_confidence"] if c else 0, confidence))
            log_good_news("whatsapp_found", company_id, f"WhatsApp: {wa_number}")

    def _looks_personal(self, email):
        """Heuristic: firstname.lastname@ or first initial patterns."""
        local = email.split("@")[0]
        parts = local.split(".")
        if len(parts) == 2 and all(p[0].islower() for p in parts if p):
            return True
        if len(local) <= 8 and local.isalpha():
            return True
        return False


# ---------------------------------------------------------------------------
# Batch enrich
# ---------------------------------------------------------------------------
def enrich_batch(company_ids, agent=None):
    """Enrich a list of company ids. Returns summary counts."""
    if agent is None:
        agent = ContactIntel()
    found = {"emails": 0, "phones": 0, "whatsapp": 0, "social": 0, "errors": 0}
    for cid in company_ids:
        r = agent.enrich_company(cid)
        if "error" in r:
            found["errors"] += 1
        else:
            found["emails"] += len(r.get("emails", []))
            found["phones"] += len(r.get("phones", []))
            found["whatsapp"] += len(r.get("whatsapp", []))
            found["social"] += r.get("social_count", 0)
    return found


# ---------------------------------------------------------------------------
# Standalone CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    from core import get_recent_agent_runs
    cintel = ContactIntel()
    if len(sys.argv) > 1:
        ids = [int(x) for x in sys.argv[1].split(",")]
    else:
        # fall back: get un-enriched companies (no email, no phone, new)
        import sqlite3
        conn = sqlite3.connect(str(__import__("core").DB_PATH))
        conn.row_factory = sqlite3.Row
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM companies WHERE status='new' AND email='' AND phone='' LIMIT 20"
        ).fetchall()]
        conn.close()
    s = enrich_batch(ids, cintel)
    print("Enrichment summary:", s)
