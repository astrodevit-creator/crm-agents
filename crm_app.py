"""
CRM Multi-Agent Desktop Application
Tkinter GUI with search, results table, company detail, export, and agent controls.
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog, simpledialog
import threading
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure crm-agents is on path
CRM_AGENTS_DIR = Path(__file__).parent
sys.path.insert(0, str(CRM_AGENTS_DIR))

from core import get_stats, get_company, get_contacts, search_companies, get_recent_agent_runs, get_good_news
from agent_company_finder import CompanyFinder
from agent_contact_intel import ContactIntel
from agent_social_scanner import SocialScanner
from agent_orchestrator import CEOAgent
from agent_crm_query import CRMQuery


class CRMApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CRM Multi-Agent System")
        self.geometry("1200x800")
        self.minsize(900, 600)
        self.configure(bg="#1a1a2e")

        # Agents
        self.finder = CompanyFinder()
        self.intel = ContactIntel()
        self.social = SocialScanner()
        self.ceo = CEOAgent()
        self.query = CRMQuery()

        # State
        self.companies_db = []  # current search results
        self.selected_company_id = None
        self.running_pipeline = False

        self._build_ui()
        self._refresh_dashboard()
        self._refresh_recent_activity()

    # ------------------------------------------------------------------
    # UI Build
    # ------------------------------------------------------------------
    def _build_ui(self):
        # Main container
        main = ttk.Frame(self, padding=0)
        main.pack(fill=tk.BOTH, expand=True)

        # Styles
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#16213e")
        style.configure("TLabel", background="#16213e", foreground="#eaeaea", font=("Segoe UI", 10))
        style.configure("TButton", background="#0f3460", foreground="white", font=("Segoe UI", 10, "bold"),
                        borderwidth=0, focuscolor="#0f3460")
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"), foreground="#e94560")
        style.configure("Accent.TButton", background="#e94560", foreground="white",
                        font=("Segoe UI", 10, "bold"))
        style.configure("Card.TFrame", background="#1a1a2e", relief="flat")
        style.configure("Field.TLabel", font=("Segoe UI", 10), foreground="#a0a0a0")
        style.configure("Value.TLabel", font=("Segoe UI", 11, "bold"), foreground="#eaeaea")

        # ---- Top bar ----
        top = ttk.Frame(main, style="TFrame")
        top.pack(fill=tk.X, padx=12, pady=(12, 4))

        ttk.Label(top, text="CRM Multi-Agent System", style="Header.TLabel").pack(side=tk.LEFT)
        self.status_label = ttk.Label(top, text="Ready", style="TLabel")
        self.status_label.pack(side=tk.RIGHT)

        # ---- Tab control ----
        tab_ctrl = ttk.Notebook(main, style="TFrame")
        tab_ctrl.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        # Tab 1 — Dashboard
        self.tab_dashboard = ttk.Frame(tab_ctrl, style="TFrame")
        tab_ctrl.add(self.tab_dashboard, text="  Dashboard  ")

        # Tab 2 — Search & Discover
        self.tab_search = ttk.Frame(tab_ctrl, style="TFrame")
        tab_ctrl.add(self.tab_search, text="  Search  ")

        # Tab 3 — Companies
        self.tab_companies = ttk.Frame(tab_ctrl, style="TFrame")
        tab_ctrl.add(self.tab_companies, text="  Companies  ")

        # Tab 4 — Activity
        self.tab_activity = ttk.Frame(tab_ctrl, style="TFrame")
        tab_ctrl.add(self.tab_activity, text="  Activity  ")

        # Tab 5 — Settings
        self.tab_settings = ttk.Frame(tab_ctrl, style="TFrame")
        tab_ctrl.add(self.tab_settings, text="  Settings  ")

        # Build each tab
        self._build_dashboard()
        self._build_search_tab()
        self._build_companies_tab()
        self._build_activity_tab()
        self._build_settings_tab()

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    def _build_dashboard(self):
        # KPI cards
        card_frame = ttk.Frame(self.tab_dashboard, style="TFrame")
        card_frame.pack(fill=tk.X, pady=8)

        self.kpi_labels = {}
        kpi_defs = [
            ("total", "Companies", "#0f3460"),
            ("email", "Emails", "#2d6a4f"),
            ("phone", "Phones", "#1b4332"),
            ("wa", "WhatsApp", "#7048e8"),
            ("ig", "Instagram", "#e1306c"),
            ("tt", "TikTok", "#00f2ea"),
            ("fb", "Facebook", "#1877f2"),
            ("li", "LinkedIn", "#0a66c2"),
        ]
        for i, (key, label, color) in enumerate(kpi_defs):
            card = ttk.Frame(card_frame, style="Card.TFrame", padding=10)
            card.grid(row=0, column=i, padx=6, sticky="nsew")
            card_frame.grid_columnconfigure(i, weight=1)
            ttk.Label(card, text=label, style="Field.TLabel").pack()
            lbl = ttk.Label(card, text="0", style="Value.TLabel", foreground=color)
            lbl.pack()
            self.kpi_labels[key] = lbl

        # Quick actions
        action_frame = ttk.Frame(self.tab_dashboard, style="TFrame")
        action_frame.pack(fill=tk.X, pady=12)

        ttk.Label(action_frame, text="Quick Actions", style="Header.TLabel").pack(anchor="w")

        act_row = ttk.Frame(action_frame, style="TFrame")
        act_row.pack(fill=tk.X, pady=4)

        self.btn_discover = ttk.Button(act_row, text="🔍 Discover Companies", style="Accent.TButton",
                                        command=self._start_discover_flow)
        self.btn_discover.pack(side=tk.LEFT, padx=4)

        self.btn_enrich_all = ttk.Button(act_row, text="📋 Enrich All Websites",
                                         command=self._enrich_all)
        self.btn_enrich_all.pack(side=tk.LEFT, padx=4)

        self.btn_scan_social = ttk.Button(act_row, text="📱 Scan Social Profiles",
                                           command=self._scan_social_all)
        self.btn_scan_social.pack(side=tk.LEFT, padx=4)

        self.btn_export = ttk.Button(act_row, text="📤 Export CSV",
                                      command=self._export_csv)
        self.btn_export.pack(side=tk.LEFT, padx=4)

        self.btn_dedupe = ttk.Button(act_row, text="🧹 Dedupe",
                                      command=self._run_dedupe)
        self.btn_dedupe.pack(side=tk.LEFT, padx=4)

        # Good news feed
        gn_frame = ttk.LabelFrame(self.tab_dashboard, text="Good News", style="TFrame",
                                   padding=8)
        gn_frame.pack(fill=tk.BOTH, expand=True, pady=8)

        self.gn_text = scrolledtext.ScrolledText(gn_frame, height=8, bg="#0d1b2a",
                                                  fg="#eaeaea", font=("Consolas", 9),
                                                  wrap=tk.WORD, borderwidth=0)
        self.gn_text.pack(fill=tk.BOTH, expand=True)

    def _refresh_dashboard(self):
        stats = get_stats()
        for key, label in [("total_companies", "total"), ("with_email", "email"),
                           ("with_phone", "phone"), ("with_whatsapp", "wa"),
                           ("with_instagram", "ig"), ("with_tiktok", "tt"),
                           ("with_facebook", "fb"), ("with_linkedin", "li")]:
            self.kpi_labels[label].config(text=str(stats.get(key, 0)))

        # Good news
        self.gn_text.config(state=tk.NORMAL)
        self.gn_text.delete("1.0", tk.END)
        news = get_good_news(unseen=True)
        if news:
            for n in news:
                ts = n["created_at"][:19] if n["created_at"] else ""
                msg = n["message"][:120] if n["message"] else ""
                kind = n["kind"]
                icon = {"company_found": "📌", "email_found": "📧", "phone_found": "📞",
                        "whatsapp_found": "💬", "social_found": "📱", "pipeline_complete": "✅",
                        "contact_found": "🔗"}.get(kind, "✨")
                line = f"{icon} [{ts}] {msg}\n"
                self.gn_text.insert(tk.END, line)
        else:
            self.gn_text.insert(tk.END, "No new activity yet.\nStart a search to see results here.")
        self.gn_text.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Search Tab
    # ------------------------------------------------------------------
    def _build_search_tab(self):
        frame = self.tab_search

        # Search box
        ttk.Label(frame, text="Find Companies", style="Header.TLabel").pack(anchor="w", pady=(8, 4))

        search_box = ttk.Frame(frame, style="TFrame")
        search_box.pack(fill=tk.X, padx=8, pady=4)

        ttk.Label(search_box, text="Keyword:", style="Field.TLabel").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_keyword = ttk.Entry(search_box, width=30, font=("Segoe UI", 11))
        self.entry_keyword.pack(side=tk.LEFT, padx=4)
        self.entry_keyword.insert(0, "coffee shop")

        ttk.Label(search_box, text="Country:", style="Field.TLabel").pack(side=tk.LEFT, padx=(12, 4))
        self.entry_country = ttk.Entry(search_box, width=15, font=("Segoe UI", 11))
        self.entry_country.pack(side=tk.LEFT, padx=4)

        ttk.Label(search_box, text="Industry:", style="Field.TLabel").pack(side=tk.LEFT, padx=(12, 4))
        self.entry_industry = ttk.Entry(search_box, width=15, font=("Segoe UI", 11))
        self.entry_industry.pack(side=tk.LEFT, padx=4)

        self.entry_max = ttk.Entry(search_box, width=6, font=("Segoe UI", 11))
        self.entry_max.pack(side=tk.LEFT, padx=(12, 4))
        self.entry_max.insert(0, "20")
        ttk.Label(search_box, text="Max:", style="Field.TLabel").pack(side=tk.LEFT, padx=(0, 4))
        # reorder
        search_box.children["!label"]._name = ""

        ttk.Button(search_box, text="🔍 Search", style="Accent.TButton",
                   command=self._do_search).pack(side=tk.LEFT, padx=8)

        ttk.Button(search_box, text="⚡ Full Pipeline (search+enrich+scan+dedupe)",
                   command=self._do_full_pipeline).pack(side=tk.LEFT, padx=8)

        # Recent searches
        ttk.Label(frame, text="Quick Keywords (click to search):", style="Field.TLabel").pack(anchor="w", pady=(16, 4))
        quick_frame = ttk.Frame(frame, style="TFrame")
        quick_frame.pack(fill=tk.X, padx=8, pady=2)

        quick_keywords = [
            "coffee shop", "restaurant", "gym", "salon", "bakery",
            "clothing store", "jewelry", "skincare", "pet shop",
            "real estate", "pharmacy", "car rental", "hotel", "spa",
            " Morocco", " France", " Spain", " Tunisia", " Canada",
        ]
        for i, kw in enumerate(quick_keywords):
            btn = ttk.Button(quick_frame, text=kw, width=14,
                             command=lambda k=kw: self._quick_search(k))
            btn.grid(row=i // 7, column=i % 7, padx=3, pady=2, sticky="n")

        # Status
        self.search_status = ttk.Label(frame, text="", style="TLabel", foreground="#a0a0a0")
        self.search_status.pack(anchor="w", pady=(8, 0))

    def _do_search(self):
        kw = self.entry_keyword.get().strip()
        country = self.entry_country.get().strip()
        industry = self.entry_industry.get().strip()
        try:
            max_r = int(self.entry_max.get())
        except ValueError:
            max_r = 20

        if not kw:
            messagebox.showwarning("Input", "Please enter a keyword to search.")
            return

        self.search_status.config(text=f"Searching for '{kw}'...", foreground="#eaeaea")
        self.update_idletasks()

        def bg():
            try:
                ids = self.finder.find_and_save(kw, country, industry, max_r)
                self.after(0, lambda: self._on_search_done(kw, ids))
            except Exception as e:
                self.after(0, lambda: self._on_search_error(str(e)))

        threading.Thread(target=bg, daemon=True).start()

    def _do_full_pipeline(self):
        kw = self.entry_keyword.get().strip()
        country = self.entry_country.get().strip()
        industry = self.entry_industry.get().strip()
        try:
            max_r = int(self.entry_max.get())
        except ValueError:
            max_r = 20

        if not kw:
            messagebox.showwarning("Input", "Please enter a keyword.")
            return

        self.search_status.config(text=f"Running full pipeline for '{kw}'...", foreground="#eaeaea")
        self.update_idletasks()

        def bg():
            try:
                result = self.ceo.run_pipeline(kw, country, industry, max_r)
                self.after(0, lambda: self._on_pipeline_done(result))
            except Exception as e:
                self.after(0, lambda: self._on_search_error(str(e)))

        threading.Thread(target=bg, daemon=True).start()

    def _quick_search(self, kw):
        self.entry_keyword.delete(0, tk.END)
        self.entry_keyword.insert(0, kw)
        self._do_search()

    def _on_search_done(self, kw, ids):
        self.search_status.config(text=f"Found {len(ids)} companies for '{kw}'.", foreground="#2d6a4f")
        self._refresh_companies_list()

    def _on_pipeline_done(self, result):
        s = result.get("enrichment", {})
        self.search_status.config(
            text=f"Pipeline done: {result.get('found',0)} companies, "
                 f"{s.get('emails',0)} emails, {s.get('phones',0)} phones, "
                 f"{s.get('whatsapp',0)} WhatsApp, {s.get('social',0)} social",
            foreground="#e94560")
        self._refresh_dashboard()
        self._refresh_companies_list()

    def _on_search_error(self, msg):
        self.search_status.config(text=f"Error: {msg}", foreground="#e94560")
        messagebox.showerror("Error", msg)

    # ------------------------------------------------------------------
    # Companies Tab
    # ------------------------------------------------------------------
    def _build_companies_tab(self):
        frame = self.tab_companies

        # Toolbar
        toolbar = ttk.Frame(frame, style="TFrame")
        toolbar.pack(fill=tk.X, padx=8, pady=4)

        ttk.Label(toolbar, text="Companies", style="Header.TLabel").pack(side=tk.LEFT)

        self.btn_refresh = ttk.Button(toolbar, text="🔄 Refresh",
                                       command=self._refresh_companies_list)
        self.btn_refresh.pack(side=tk.LEFT, padx=8)

        self.btn_enrich_sel = ttk.Button(toolbar, text="📋 Enrich Selected",
                                          command=self._enrich_selected)
        self.btn_enrich_sel.pack(side=tk.LEFT, padx=4)

        self.btn_scan_sel = ttk.Button(toolbar, text="📱 Scan Social Selected",
                                        command=self._scan_social_selected)
        self.btn_scan_sel.pack(side=tk.LEFT, padx=4)

        self.btn_del_sel = ttk.Button(toolbar, text="🗑 Delete Selected",
                                       command=self._delete_selected)
        self.btn_del_sel.pack(side=tk.LEFT, padx=4)

        # Filter bar
        filter_bar = ttk.Frame(frame, style="TFrame")
        filter_bar.pack(fill=tk.X, padx=8, pady=2)

        ttk.Label(filter_bar, text="Filter:", style="Field.TLabel").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_filter = ttk.Entry(filter_bar, width=30, font=("Segoe UI", 10))
        self.entry_filter.pack(side=tk.LEFT, padx=4)
        self.entry_filter.bind("<KeyRelease>", lambda e: self._filter_companies())

        ttk.Label(filter_bar, text="By country:", style="Field.TLabel").pack(side=tk.LEFT, padx=(12, 4))
        self.entry_filter_country = ttk.Entry(filter_bar, width=12, font=("Segoe UI", 10))
        self.entry_filter_country.pack(side=tk.LEFT, padx=4)
        self.entry_filter_country.bind("<KeyRelease>", lambda e: self._filter_companies())

        # Treeview
        tree_frame = ttk.Frame(frame, style="TFrame")
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        cols = ("id", "name", "website", "country", "industry", "email", "phone",
                "whatsapp", "instagram", "tiktok", "facebook", "linkedin", "score", "status")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=15)
        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="Company")
        self.tree.heading("website", text="Website")
        self.tree.heading("country", text="Country")
        self.tree.heading("industry", text="Industry")
        self.tree.heading("email", text="Email")
        self.tree.heading("phone", text="Phone")
        self.tree.heading("whatsapp", text="WhatsApp")
        self.tree.heading("instagram", text="Instagram")
        self.tree.heading("tiktok", text="TikTok")
        self.tree.heading("facebook", text="Facebook")
        self.tree.heading("linkedin", text="LinkedIn")
        self.tree.heading("score", text="Score")
        self.tree.heading("status", text="Status")

        self.tree.column("id", width=40, anchor="center")
        self.tree.column("name", width=180, minwidth=100)
        self.tree.column("website", width=150, minwidth=80)
        self.tree.column("country", width=80)
        self.tree.column("industry", width=100)
        self.tree.column("email", width=160, minwidth=80)
        self.tree.column("phone", width=100)
        self.tree.column("whatsapp", width=100)
        self.tree.column("instagram", width=100)
        self.tree.column("tiktok", width=80)
        self.tree.column("facebook", width=100)
        self.tree.column("linkedin", width=100)
        self.tree.column("score", width=50, anchor="center")
        self.tree.column("status", width=80, anchor="center")

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Detail panel
        detail_frame = ttk.LabelFrame(frame, text="Company Details", style="TFrame", padding=8)
        detail_frame.pack(fill=tk.X, padx=8, pady=4)

        self.detail_text = scrolledtext.ScrolledText(detail_frame, height=6, bg="#0d1b2a",
                                                      fg="#eaeaea", font=("Consolas", 9),
                                                      wrap=tk.WORD, borderwidth=0, state=tk.DISABLED)
        self.detail_text.pack(fill=tk.X, expand=True)

        # Bind events
        self.tree.bind("<<TreeviewSelect>>", self._on_company_select)
        self.tree.bind("<Double-1>", self._on_company_double_click)

        self._refresh_companies_list()

    def _refresh_companies_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Get all companies (or filtered)
        q = self.entry_filter.get().strip()
        country = self.entry_filter_country.get().strip()

        if q:
            rows = search_companies(q, 500, 0, {"country": country} if country else None)
        else:
            import sqlite3 as _sqlite
            conn = _sqlite.connect(str(__import__("core").DB_PATH))
            conn.row_factory = _sqlite.Row
            try:
                base = "SELECT * FROM companies ORDER BY opportunity_score DESC"
                params = []
                if country:
                    base += " WHERE country = ?"
                    params = [country]
                rows = conn.execute(base, params).fetchall()
            finally:
                conn.close()
            rows = [r for r in rows]

        self.companies_db = [dict(r) for r in rows]

        for c in self.companies_db:
            vals = [
                c.get("id"), c.get("name"), c.get("website"), c.get("country"),
                c.get("industry"), c.get("email"), c.get("phone"),
                c.get("whatsapp"), c.get("instagram"), c.get("tiktok"),
                c.get("facebook"), c.get("linkedin"),
                c.get("opportunity_score", 0), c.get("status", "new"),
            ]
            self.tree.insert("", tk.END, values=vals)

        if not self.companies_db:
            self.tree.insert("", tk.END, values=("--", "No companies found", "", "", "", "", "", "", "", "", "", "", "", ""))

    def _filter_companies(self):
        self._refresh_companies_list()

    def _on_company_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        item = self.tree.item(sel[0])
        vals = item["values"]
        cid = vals[0]
        if cid and cid != "--":
            self.selected_company_id = int(cid)
            self._show_company_detail(self.selected_company_id)
        else:
            self.selected_company_id = None
            self.detail_text.config(state=tk.NORMAL)
            self.detail_text.delete("1.0", tk.END)
            self.detail_text.insert(tk.END, "Select a company to see details.")
            self.detail_text.config(state=tk.DISABLED)

    def _on_company_double_click(self, event):
        self._on_company_select(event)

    def _show_company_detail(self, cid):
        company = get_company(cid)
        if not company:
            return
        contacts = get_contacts(cid)

        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)

        lines = []
        lines.append(f"═" * 60)
        lines.append(f"  {company['name']}")
        lines.append(f"  ID: {cid}  |  Status: {company['status'] or 'new'}")
        lines.append(f"  Score: {company['opportunity_score'] or 0}/100")
        lines.append(f"═" * 60)
        lines.append("")
        lines.append(f"  Website:  {company['website'] or '—'}")
        lines.append(f"  Domain:   {company['domain'] or '—'}")
        lines.append(f"  Country:  {company['country'] or '—'}")
        lines.append(f"  City:     {company['city'] or '—'}")
        lines.append(f"  Industry: {company['industry'] or '—'}")
        lines.append(f"  Size:     {company['est_size'] or '—'}")
        lines.append(f"  Founded:  {company['founded_year'] or '—'}")
        lines.append(f"  Revenue:  {company['revenue_range'] or '—'}")
        lines.append(f"  Employees: {company['employees_min'] or '—'} — {company['employees_max'] or '—'}")
        lines.append("")
        lines.append(f"  Decision Maker: {company['decision_maker'] or '—'}")
        lines.append(f"  DM Title:       {company['dm_title'] or '—'}")
        lines.append(f"  DM Email:       {company['dm_email'] or '—'}")
        lines.append(f"  DM Phone:       {company['dm_phone'] or '—'}")
        lines.append("")
        lines.append(f"  Primary Contact: {company['primary_contact'] or '—'}")
        lines.append(f"  Contact Confidence: {company['contact_confidence'] or 0:.0%}")
        lines.append("")
        lines.append(f"  ── Contacts ──")

        for ct in contacts:
            lines.append(f"  [{ct['type'].upper()}] {ct['value']}  (confidence: {ct['confidence'] or 0:.0%}, source: {ct['source'] or '—'})")

        if not contacts:
            lines.append("  (no contacts found)")

        lines.append("")
        lines.append(f"  ── Social ──")
        for plat in ["instagram", "tiktok", "facebook", "linkedin", "twitter", "youtube"]:
            val = company.get(plat, "")
            if val:
                lines.append(f"  {plat.upper():<12}: {val}")

        lines.append("")
        lines.append(f"  Source: {company['source'] or '—'}")
        if company.get("source_url"):
            lines.append(f"  Source URL: {company['source_url']}")
        lines.append("")
        lines.append(f"  Notes: {company['notes'] or '—'}")
        lines.append("")
        lines.append(f"  Created: {company['created_at'][:19] if company['created_at'] else '—'}")
        lines.append(f"  Updated: {company['updated_at'][:19] if company['updated_at'] else '—'}")
        lines.append(f"═" * 60)

        text = "\n".join(lines)
        self.detail_text.insert(tk.END, text)
        self.detail_text.config(state=tk.DISABLED)

    def _enrich_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select a company first.")
            return
        cid = int(self.tree.item(sel[0])["values"][0])
        if cid == "--":
            return
        self._run_agent_on_company(cid, self.intel.enrich_company, "Enriching...")

    def _scan_social_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select a company first.")
            return
        cid = int(self.tree.item(sel[0])["values"][0])
        if cid == "--":
            return
        self._run_agent_on_company(cid, self.social.scan_company, "Scanning social...")

    def _delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select a company first.")
            return
        cid = int(self.tree.item(sel[0])["values"][0])
        if cid == "--":
            return
        if messagebox.askyesno("Delete", f"Delete company #{cid}? This cannot be undone."):
            import sqlite3 as _sqlite
            conn = _sqlite.connect(str(__import__("core").DB_PATH))
            try:
                conn.execute("DELETE FROM companies WHERE id=?", (cid,))
                conn.commit()
            finally:
                conn.close()
            self._refresh_companies_list()

    def _run_agent_on_company(self, cid, agent_fn, status_text):
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert(tk.END, f"{status_text} #{cid}\n\nWorking...")
        self.detail_text.config(state=tk.DISABLED)
        self.update_idletasks()

        def bg():
            try:
                result = agent_fn(cid)
                self.after(0, lambda: self._on_agent_done(cid, result))
            except Exception as e:
                self.after(0, lambda: self._on_agent_error(cid, str(e)))

        threading.Thread(target=bg, daemon=True).start()

    def _on_agent_done(self, cid, result):
        self._refresh_companies_list()
        if cid == self.selected_company_id:
            self._show_company_detail(cid)
        self._refresh_dashboard()
        messagebox.showinfo("Done", f"Agent completed for #{cid}.\nResult: {json.dumps(result, default=str)[:300]}")

    def _on_agent_error(self, cid, msg):
        self._refresh_companies_list()
        messagebox.showerror("Error", f"Agent failed for #{cid}: {msg}")

    # ------------------------------------------------------------------
    # Activity Tab
    # ------------------------------------------------------------------
    def _build_activity_tab(self):
        frame = self.tab_activity
        ttk.Label(frame, text="Agent Activity Log", style="Header.TLabel").pack(anchor="w", pady=(8, 4))

        activity_frame = ttk.Frame(frame, style="TFrame")
        activity_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self.activity_text = scrolledtext.ScrolledText(activity_frame, height=20, bg="#0d1b2a",
                                                        fg="#eaeaea", font=("Consolas", 9),
                                                        wrap=tk.WORD, borderwidth=0)
        self.activity_text.pack(fill=tk.BOTH, expand=True)

        btn_frame = ttk.Frame(frame, style="TFrame")
        btn_frame.pack(fill=tk.X, padx=8, pady=4)

        ttk.Button(btn_frame, text="🔄 Refresh", command=self._refresh_recent_activity).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="🗑 Clear", command=self._clear_activity).pack(side=tk.LEFT, padx=4)

        self._refresh_recent_activity()

    def _refresh_recent_activity(self):
        self.activity_text.config(state=tk.NORMAL)
        self.activity_text.delete("1.0", tk.END)

        runs = get_recent_agent_runs(100)
        if not runs:
            self.activity_text.insert(tk.END, "No activity recorded yet.\n")
        else:
            for r in reversed(runs):
                ts = r["created_at"][:19] if r["created_at"] else ""
                agent = r["agent"][:12]
                action = r["action"][:25]
                detail = (r["detail"] or "")[:60]
                result_preview = (r["result"] or "")[:80]
                line = f"[{ts}] {agent:<12} | {action:<25} | {detail}\n"
                if result_preview and result_preview != "null":
                    line += f"         → {result_preview}\n"
                self.activity_text.insert(tk.END, line)

        self.activity_text.config(state=tk.DISABLED)

    def _clear_activity(self):
        self.activity_text.config(state=tk.NORMAL)
        self.activity_text.delete("1.0", tk.END)
        self.activity_text.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Settings Tab
    # ------------------------------------------------------------------
    def _build_settings_tab(self):
        frame = self.tab_settings

        ttk.Label(frame, text="Agent Settings", style="Header.TLabel").pack(anchor="w", pady=(8, 4))

        settings = [
            ("Max results per search", "max_search", "20"),
            ("Enrich timeout (sec)", "enrich_timeout", "20"),
            ("Social scan timeout (sec)", "social_timeout", "8"),
            ("Loop interval (sec)", "loop_interval", "300"),
            ("Max companies per loop cycle", "loop_max", "10"),
        ]

        self.setting_vars = {}
        row = 0
        for label, key, default in settings:
            sf = ttk.Frame(frame, style="TFrame")
            sf.pack(fill=tk.X, padx=16, pady=3)

            ttk.Label(sf, text=label, style="Field.TLabel", width=28, anchor="w").pack(side=tk.LEFT)
            var = tk.StringVar(value=default)
            entry = ttk.Entry(sf, width=10, textvariable=var, font=("Segoe UI", 10))
            entry.pack(side=tk.LEFT, padx=4)
            self.setting_vars[key] = var

            row += 1

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=16, pady=12)

        ttk.Label(frame, text="Database Info", style="Header.TLabel").pack(anchor="w", pady=(4, 4))

        db_info = ttk.Frame(frame, style="TFrame")
        db_info.pack(fill=tk.X, padx=16)

        from core import DB_PATH
        ttk.Label(db_info, text=f"Database: {DB_PATH}", style="Field.TLabel", wraplength=600).pack(anchor="w")
        ttk.Label(db_info, text="Location: ~/.crm_agents/agent_crm.db", style="Field.TLabel").pack(anchor="w")

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=16, pady=12)

        ttk.Label(frame, text="Export Options", style="Header.TLabel").pack(anchor="w", pady=(4, 4))

        exp_frame = ttk.Frame(frame, style="TFrame")
        exp_frame.pack(fill=tk.X, padx=16, pady=4)

        ttk.Button(exp_frame, text="📤 Export All as CSV", command=self._export_csv).pack(side=tk.LEFT, padx=4)
        ttk.Button(exp_frame, text="📤 Export All as XLSX", command=self._export_xlsx).pack(side=tk.LEFT, padx=4)
        ttk.Button(exp_frame, text="📤 Export All as JSON", command=self._export_json).pack(side=tk.LEFT, padx=4)

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=16, pady=12)

        ttk.Label(frame, text="Agent System Info", style="Header.TLabel").pack(anchor="w", pady=(4, 4))

        info_frame = ttk.Frame(frame, style="TFrame")
        info_frame.pack(fill=tk.X, padx=16)

        info_text = (
            "CRM Multi-Agent System v1.0\n"
            "Agents:\n"
            "  • CompanyFinder — searches web for companies matching keywords\n"
            "  • ContactIntel — visits websites, extracts emails, phones, WhatsApp\n"
            "  • SocialScanner — finds Instagram, TikTok, Facebook, LinkedIn, Twitter, YouTube\n"
            "  • CRMQuery — full-text search, filter, export (CSV/XLSX/JSON)\n"
            "  • Deduper — finds and merges duplicate companies\n"
            "  • CEO — orchestrates the full pipeline\n\n"
            "Database: SQLite (WAL mode) with full-text search (FTS5)"
        )
        ttk.Label(info_frame, text=info_text, style="Field.TLabel", justify=tk.LEFT,
                  wraplength=700).pack(anchor="w")

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=16, pady=12)

        ttk.Button(frame, text="🔄 Refresh Dashboard", command=self._refresh_dashboard).pack(pady=8)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export Companies to CSV"
        )
        if not path:
            return
        try:
            result = self.query.export_csv(path=path)
            messagebox.showinfo("Exported", f"Exported to:\n{result}")
            self._refresh_dashboard()
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _export_xlsx(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            title="Export Companies to Excel"
        )
        if not path:
            return
        try:
            result = self.query.export_xlsx(path=path)
            if result:
                messagebox.showinfo("Exported", f"Exported to:\n{result}")
            else:
                messagebox.showwarning("Export", "openpyxl not available. Install with: uv pip install openpyxl")
            self._refresh_dashboard()
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _export_json(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Export Companies to JSON"
        )
        if not path:
            return
        try:
            result = self.query.export_json(path=path)
            messagebox.showinfo("Exported", f"Exported to:\n{result}")
            self._refresh_dashboard()
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    # ------------------------------------------------------------------
    # Batch operations
    # ------------------------------------------------------------------
    def _start_discover_flow(self):
        # Open a dialog to collect search parameters
        dlg = tk.Toplevel(self)
        dlg.title("Discover Companies")
        dlg.geometry("450x320")
        dlg.configure(bg="#16213e")
        dlg.transient(self)
        dlg.grab_set()

        ttk.Label(dlg, text="Discover New Companies", style="Header.TLabel", background="#16213e").pack(pady=12)

        fields = []
        for label, default, width in [
            ("Keyword(s) (comma-separated)", "coffee shop,restaurant,gym", 40),
            ("Country", "", 20),
            ("Industry", "", 20),
            ("Max per keyword", "15", 8),
        ]:
            f = ttk.Frame(dlg, style="TFrame")
            f.pack(fill=tk.X, padx=20, pady=3)
            ttk.Label(f, text=label, style="Field.TLabel", width=22, anchor="w").pack(side=tk.LEFT)
            entry = ttk.Entry(f, width=width, font=("Segoe UI", 11))
            entry.pack(side=tk.LEFT, padx=4)
            entry.insert(0, default)
            fields.append(entry)

        result_label = ttk.Label(dlg, text="", style="TLabel", foreground="#a0a0a0", background="#16213e")
        result_label.pack(pady=8)

        def start():
            keywords = fields[0].get().split(",")
            country = fields[1].get().strip()
            industry = fields[2].get().strip()
            try:
                max_r = int(fields[3].get())
            except ValueError:
                max_r = 15

            result_label.config(text="Running discovery...", foreground="#eaeaea")
            dlg.update_idletasks()

            def bg():
                try:
                    all_ids = []
                    for kw in keywords:
                        kw = kw.strip()
                        if not kw:
                            continue
                        ids = self.finder.find_and_save(kw, country, industry, max_r)
                        all_ids.extend(ids)
                    self.after(0, lambda: result_label.config(
                        text=f"Found {len(all_ids)} companies across {len(keywords)} keywords.",
                        foreground="#2d6a4f"))
                    self._refresh_dashboard()
                    self._refresh_companies_list()
                except Exception as e:
                    self.after(0, lambda: result_label.config(
                        text=f"Error: {e}", foreground="#e94560"))

            threading.Thread(target=bg, daemon=True).start()

        ttk.Button(dlg, text="▶ Start Discovery", style="Accent.TButton", command=start).pack(pady=12, padx=20)

    def _enrich_all(self):
        if messagebox.askyesno("Enrich All",
                                "Visit ALL company websites and extract emails, phones, WhatsApp?\n"
                                "This may take a while. Continue?"):
            self.status_label.config(text="Enriching all...")
            self.update_idletasks()

            import sqlite3 as _sqlite
            conn = _sqlite.connect(str(__import__("core").DB_PATH))
            conn.row_factory = _sqlite.Row
            try:
                rows = conn.execute(
                    "SELECT id FROM companies WHERE website != '' AND (email='' OR phone='') LIMIT 100"
                ).fetchall()
                ids = [r["id"] for r in rows]
            finally:
                conn.close()

            if not ids:
                messagebox.showinfo("Enrich", "Nothing to enrich (all websites processed or no websites).")
                self.status_label.config(text="Ready")
                return

            self.status_label.config(text=f"Enriching {len(ids)} companies...")

            def bg():
                try:
                    s = enrich_batch(ids, self.intel)
                    self.after(0, lambda: self._on_enrich_all_done(s))
                except Exception as e:
                    self.after(0, lambda: self._on_enrich_all_error(str(e)))

            threading.Thread(target=bg, daemon=True).start()

    def _on_enrich_all_done(self, s):
        self.status_label.config(text="Ready")
        self._refresh_dashboard()
        self._refresh_companies_list()
        self._refresh_dashboard()
        messagebox.showinfo("Enrichment Complete",
                            f"Emails found: {s['emails']}\n"
                            f"Phones found: {s['phones']}\n"
                            f"WhatsApp found: {s['whatsapp']}\n"
                            f"Social profiles: {s['social']}\n"
                            f"Errors: {s['errors']}")

    def _on_enrich_all_error(self, msg):
        self.status_label.config(text="Ready")
        messagebox.showerror("Error", msg)

    def _scan_social_all(self):
        if messagebox.askyesno("Scan Social",
                                "Scan ALL companies for Instagram, TikTok, Facebook, LinkedIn, Twitter, YouTube?\n"
                                "Continue?"):
            self.status_label.config(text="Scanning social...")
            self.update_idletasks()

            import sqlite3 as _sqlite
            conn = _sqlite.connect(str(__import__("core").DB_PATH))
            conn.row_factory = _sqlite.Row
            try:
                rows = conn.execute(
                    "SELECT id FROM companies WHERE (instagram='' AND tiktok='' AND facebook='' "
                    "AND linkedin='' AND twitter='' AND youtube='') LIMIT 100"
                ).fetchall()
                ids = [r["id"] for r in rows]
            finally:
                conn.close()

            if not ids:
                messagebox.showinfo("Scan", "Nothing to scan (all profiles found or no companies).")
                self.status_label.config(text="Ready")
                return

            self.status_label.config(text=f"Scanning {len(ids)} companies...")

            def bg():
                try:
                    s = scan_batch(ids, self.social)
                    self.after(0, lambda: self._on_scan_all_done(s))
                except Exception as e:
                    self.after(0, lambda: self._on_scan_all_error(str(e)))

            threading.Thread(target=bg, daemon=True).start()

    def _on_scan_all_done(self, s):
        self.status_label.config(text="Ready")
        self._refresh_dashboard()
        self._refresh_companies_list()
        messagebox.showinfo("Social Scan Complete",
                            f"Companies scanned: {s['companies_scanned']}\n"
                            f"Platforms found: {s['platforms']}")

    def _on_scan_all_error(self, msg):
        self.status_label.config(text="Ready")
        messagebox.showerror("Error", msg)

    def _run_dedupe(self):
        if messagebox.askyesno("Dedupe",
                                "Find and merge duplicate companies?\n"
                                "Duplicates are detected by exact domain match and similar names.\n"
                                "Continue?"):
            self.status_label.config(text="Deduping...")
            self.update_idletasks()

            def bg():
                try:
                    s = self.ceo.dedup.dedupe_batch()
                    self.after(0, lambda: self._on_dedupe_done(s))
                except Exception as e:
                    self.after(0, lambda: self._on_dedupe_error(str(e)))

            threading.Thread(target=bg, daemon=True).start()

    def _on_dedupe_done(self, s):
        self.status_label.config(text="Ready")
        self._refresh_dashboard()
        self._refresh_companies_list()
        messagebox.showinfo("Dedupe Complete",
                            f"Duplicate pairs found: {s['pairs']}\n"
                            f"Merged: {s['merged']}\n"
                            f"Skipped: {s['skipped']}")

    def _on_dedupe_error(self, msg):
        self.status_label.config(text="Ready")
        messagebox.showerror("Error", msg)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Ensure DB is initialized even if run directly
    import core
    core.init_db()
    app = CRMApp()
    app.mainloop()
