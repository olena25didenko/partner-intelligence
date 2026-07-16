"""
Infinitopes Partner Intelligence Dashboard
Live monitoring of Tier 1-2 pharma partners via free public APIs.

Data sources (all free):
  - ClinicalTrials.gov API v2 (clinical trials)
  - SEC EDGAR (public company filings)
  - FDA and EMA RSS (regulatory announcements)
  - Google News RSS (press releases and news)

No API keys required. Deploy on Streamlit Community Cloud (free).
"""
import re
import html
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import feedparser
import requests
import streamlit as st
import yaml

# =========================================================================
# CONFIG
# =========================================================================
st.set_page_config(
    page_title="Infinitopes Partner Intelligence",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Infinitopes brand palette
NAVY = "#1A19A5"
TEAL_PETROL = "#015579"
TEAL = "#348591"
TEAL_LIGHT = "#37BFA9"
AMBER = "#F4B913"
BG = "#EAF7FD"
INK = "#1F2A44"
GREY = "#6B7280"

st.markdown(f"""
<style>
    :root {{
        --navy: {NAVY};
        --teal: {TEAL};
        --teal-light: {TEAL_LIGHT};
        --amber: {AMBER};
    }}
    .stApp header {{ background: transparent; }}
    h1 {{ color: {NAVY} !important; }}
    h2, h3 {{ color: {TEAL_PETROL} !important; }}
    section[data-testid="stSidebar"] {{ background: {BG}; }}
    section[data-testid="stSidebar"] h1 {{ color: {NAVY} !important; }}
    .item-card {{
        background: white;
        border-left: 4px solid {TEAL};
        border-radius: 6px;
        padding: 12px 16px;
        margin-bottom: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }}
    .item-title {{
        color: {NAVY}; font-weight: 600; font-size: 1.02em;
        margin-bottom: 4px;
    }}
    .item-meta {{ color: {GREY}; font-size: 0.83em; }}
    .item-body {{ margin-top: 6px; font-size: 0.92em; color: {INK}; }}
    .item-link a {{ color: {TEAL_PETROL}; font-weight: 500; }}
    .stat-pill {{
        display: inline-block; padding: 3px 10px; border-radius: 12px;
        background: {BG}; color: {TEAL_PETROL}; margin-right: 6px;
        font-size: 0.85em; font-weight: 600;
    }}
    div[data-testid="stMetricValue"] {{ color: {NAVY}; }}
    div[data-testid="stMetricLabel"] {{ color: {GREY}; }}
    button[role="tab"][aria-selected="true"] {{
        color: {NAVY} !important;
        border-bottom-color: {TEAL} !important;
    }}
    .stButton>button {{
        background-color: {TEAL_PETROL}; color: white;
        border: none; border-radius: 6px;
    }}
    .stButton>button:hover {{ background-color: {NAVY}; }}
</style>
""", unsafe_allow_html=True)

USER_AGENT = "Infinitopes Partner Intelligence Dashboard (contact via LinkedIn)"


# =========================================================================
# DATA LOADERS
# =========================================================================
@st.cache_data(ttl=86400)
def load_config():
    with open("partners.yaml", "r") as f:
        return yaml.safe_load(f)


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_trials(sponsor: str, indications: list, months_back: int = 12) -> list:
    """Query ClinicalTrials.gov API v2 for studies by sponsor in given indications."""
    if not sponsor:
        return []
    url = "https://clinicaltrials.gov/api/v2/studies"
    cutoff = (datetime.now(timezone.utc) - timedelta(days=months_back * 30)).strftime("%Y-%m-%d")
    cond_query = " OR ".join(f'"{i}"' for i in indications) if indications else ""
    params = {
        "query.spons": sponsor,
        "pageSize": 50,
        "format": "json",
        "sort": "LastUpdatePostDate:desc",
        "filter.advanced": f"AREA[LastUpdatePostDate]RANGE[{cutoff},MAX]",
    }
    if cond_query:
        params["query.cond"] = cond_query
    try:
        r = requests.get(url, params=params, timeout=25,
                         headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        studies = r.json().get("studies", [])
    except Exception as e:
        return [{"error": f"{type(e).__name__}: {e}"}]
    out = []
    for s in studies:
        p = s.get("protocolSection", {})
        idmod = p.get("identificationModule", {})
        status_mod = p.get("statusModule", {})
        design_mod = p.get("designModule", {})
        conds_mod = p.get("conditionsModule", {})
        nct_id = idmod.get("nctId")
        out.append({
            "nct_id": nct_id,
            "title": idmod.get("briefTitle", ""),
            "status": status_mod.get("overallStatus", "UNKNOWN"),
            "phase": ", ".join(design_mod.get("phases", []) or ["N/A"]),
            "conditions": ", ".join(conds_mod.get("conditions", [])[:3]),
            "last_updated": status_mod.get("lastUpdatePostDateStruct", {}).get("date", ""),
            "start_date": status_mod.get("startDateStruct", {}).get("date", ""),
            "url": f"https://clinicaltrials.gov/study/{nct_id}",
        })
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_sec_filings(cik: str, max_items: int = 20) -> list:
    """Fetch recent SEC filings via EDGAR submissions API."""
    if not cik or not str(cik).strip():
        return []
    cik_str = str(cik).strip()
    cik_padded = cik_str.zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    form_types = {"10-K", "10-Q", "8-K", "20-F", "6-K", "S-1", "10-K/A", "10-Q/A"}
    try:
        r = requests.get(url, timeout=20,
                         headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return [{"error": f"{type(e).__name__}: {e}"}]
    recent = data.get("filings", {}).get("recent", {})
    if not recent:
        return []
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accession = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    descriptions = recent.get("primaryDocDescription", [])
    out = []
    for i in range(len(forms)):
        if forms[i] not in form_types:
            continue
        acc_no_dashes = accession[i].replace("-", "")
        cik_int = int(cik_str)
        out.append({
            "form": forms[i],
            "date": dates[i],
            "desc": descriptions[i] if i < len(descriptions) else "",
            "url": f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_no_dashes}/{primary_docs[i]}",
            "index_url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_int}&type={forms[i]}&dateb=&owner=include&count=10",
        })
        if len(out) >= max_items:
            break
    return out


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_rss(url: str, max_items: int = 25) -> list:
    """Fetch and parse an RSS feed."""
    try:
        feed = feedparser.parse(url, agent=USER_AGENT)
    except Exception as e:
        return [{"error": f"{type(e).__name__}: {e}"}]
    if feed.get("bozo") and not feed.entries:
        return [{"error": f"Feed error: {feed.get('bozo_exception', 'unknown')}"}]
    out = []
    for entry in feed.entries[:max_items]:
        summary = re.sub(r"<[^>]+>", "", entry.get("summary", ""))[:400]
        out.append({
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "published": entry.get("published", entry.get("updated", "")),
            "summary": summary,
            "source": entry.get("source", {}).get("title", "") if isinstance(entry.get("source"), dict) else "",
        })
    return out


def google_news_url(query: str) -> str:
    """Build a Google News RSS URL for a search query."""
    q = quote_plus(query)
    return f"https://news.google.com/rss/search?q={q}&hl=en-GB&gl=GB&ceid=GB:en"


def filter_by_terms(items: list, terms: list) -> list:
    """Filter RSS items to those mentioning any of the given terms."""
    if not terms:
        return items
    lower_terms = [t.lower() for t in terms if t]
    keep = []
    for it in items:
        blob = (it.get("title", "") + " " + it.get("summary", "")).lower()
        if any(t in blob for t in lower_terms):
            keep.append(it)
    return keep


# =========================================================================
# UI
# =========================================================================
config = load_config()
partners = config["partners"]
partner_names = [p["name"] for p in partners]
partner_by_name = {p["name"]: p for p in partners}
default_indications = config.get("default_indications", [
    "oesophageal cancer", "esophageal cancer", "gastric cancer",
    "immunotherapy", "cancer vaccine", "neoantigen",
])

# --- Sidebar ---
with st.sidebar:
    st.markdown("# 🧬 Partner Intelligence")
    st.caption("Live feed for Tier 1-2 pharma partners")
    st.divider()

    selected_partner_name = st.selectbox(
        "Partner", partner_names, index=0,
        help="Add or remove partners in partners.yaml"
    )
    partner = partner_by_name[selected_partner_name]

    st.markdown("### Filter by indication")
    indications = st.multiselect(
        "Terms",
        options=default_indications,
        default=default_indications,
        help="Used for the ClinicalTrials.gov query and the indication-scoped news feed",
        label_visibility="collapsed",
    )

    months_back = st.slider("Look back (months)", 1, 24, 6,
                             help="Applied to trials and news")

    st.divider()
    if st.button("🔄 Refresh all data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.caption("Cached 30-60 min. Refresh forces a live pull.")
    st.divider()
    st.caption("Sources: ClinicalTrials.gov · SEC EDGAR · FDA/EMA RSS · Google News. All free.")

# --- Main header ---
st.markdown(f"# {partner['name']}")

hdr_cols = st.columns([1.2, 1.2, 1.6, 1.6, 1.2])
hdr_cols[0].metric("Ticker", partner.get("ticker", "—"))
hdr_cols[1].metric("HQ", partner.get("hq", "—"))
hdr_cols[2].metric("Our focus", partner.get("focus", "—")[:26])
hdr_cols[3].metric("Our contact", partner.get("our_contact", "—")[:26])
hdr_cols[4].metric("Tier", partner.get("tier", "—"))

st.markdown(
    f"[Website ↗]({partner['website']})  ·  "
    f"Last page refresh: **{datetime.now().strftime('%Y-%m-%d %H:%M UTC')}**"
)

tab_trials, tab_sec, tab_reg, tab_press = st.tabs([
    "🧪 Clinical trials",
    "📄 SEC filings",
    "🏛️ FDA / EMA",
    "📰 Press & news",
])

# --------------------------- Trials tab ---------------------------
with tab_trials:
    st.markdown("### ClinicalTrials.gov studies")
    st.caption(
        f"Sponsor: **{partner['name']}** · updated in last **{months_back}** months · "
        f"filtered on **{len(indications)}** indication terms"
    )
    with st.spinner("Querying ClinicalTrials.gov..."):
        trials = fetch_trials(partner["name"], indications, months_back)

    if trials and trials[0].get("error"):
        st.error(f"ClinicalTrials.gov API error: {trials[0]['error']}")
    elif not trials:
        st.info("No matching trials in this window. Try widening the look-back or removing indication filters.")
    else:
        # Quick stats
        from collections import Counter
        phases = Counter()
        statuses = Counter()
        for t in trials:
            for ph in [x.strip() for x in t["phase"].split(",")]:
                if ph and ph != "N/A":
                    phases[ph] += 1
            statuses[t["status"]] += 1

        stat_html = f"<span class='stat-pill'>{len(trials)} matching studies</span>"
        for ph, n in sorted(phases.items(), reverse=True):
            stat_html += f"<span class='stat-pill'>{n} {ph}</span>"
        for status, n in sorted(statuses.items(), key=lambda x: -x[1])[:3]:
            stat_html += f"<span class='stat-pill'>{n} {status}</span>"
        st.markdown(stat_html, unsafe_allow_html=True)
        st.write("")

        for t in trials:
            title = html.escape(t["title"])
            conditions = html.escape(t["conditions"])
            st.markdown(f"""
<div class="item-card">
  <div class="item-title">{title}</div>
  <div class="item-meta">
    <b>{t['nct_id']}</b> · {t['phase']} · <b>{t['status']}</b> ·
    updated {t['last_updated']} · started {t['start_date'] or 'n/a'}
  </div>
  <div class="item-body">{conditions}</div>
  <div class="item-link" style="margin-top: 6px;">
    <a href="{t['url']}" target="_blank">Open on ClinicalTrials.gov ↗</a>
  </div>
</div>
""", unsafe_allow_html=True)

# --------------------------- SEC tab ---------------------------
with tab_sec:
    st.markdown("### SEC EDGAR filings")
    cik = partner.get("cik", "").strip()
    if not cik:
        st.info(
            f"**{partner['name']}** is not SEC-registered ("
            "listed outside the US or not publicly traded). "
            "No EDGAR data available. Check the Press & News tab for updates."
        )
    else:
        st.caption(f"CIK: **{cik}** · showing recent 10-K, 10-Q, 8-K, 20-F, 6-K, S-1")
        with st.spinner("Querying SEC EDGAR..."):
            filings = fetch_sec_filings(cik)
        if filings and filings[0].get("error"):
            st.error(f"SEC EDGAR API error: {filings[0]['error']}")
        elif not filings:
            st.info("No recent filings found.")
        else:
            st.markdown(f"<span class='stat-pill'>{len(filings)} recent filings</span>",
                         unsafe_allow_html=True)
            st.write("")
            for f in filings[:15]:
                desc = html.escape(f.get("desc") or f["form"])
                st.markdown(f"""
<div class="item-card">
  <div class="item-title">Form {f['form']}</div>
  <div class="item-meta">Filed <b>{f['date']}</b> · {desc}</div>
  <div class="item-link" style="margin-top: 6px;">
    <a href="{f['url']}" target="_blank">Open filing ↗</a> ·
    <a href="{f['index_url']}" target="_blank">Filing history</a>
  </div>
</div>
""", unsafe_allow_html=True)

# --------------------------- FDA / EMA tab ---------------------------
with tab_reg:
    st.markdown("### FDA & EMA announcements")
    st.caption("Live regulatory RSS feeds, then filtered by partner name or selected indications.")

    fda_url = "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-announcements/rss.xml"
    ema_url = "https://www.ema.europa.eu/en/rss.xml"
    filter_terms = [partner["name"]] + indications

    reg_col_1, reg_col_2 = st.columns(2)
    with reg_col_1:
        st.markdown("#### FDA press announcements")
        with st.spinner("Fetching FDA..."):
            fda = fetch_rss(fda_url)
        if fda and fda[0].get("error"):
            st.warning(f"FDA feed unavailable: {fda[0]['error']}")
        else:
            filtered = filter_by_terms(fda, filter_terms)
            if filtered:
                st.markdown(f"<span class='stat-pill'>{len(filtered)} matching FDA items</span>",
                             unsafe_allow_html=True)
                for item in filtered[:12]:
                    title = html.escape(item["title"])
                    st.markdown(
                        f"**[{title}]({item['link']})**  \n"
                        f"<span style='color:{GREY}; font-size:0.85em;'>{item['published']}</span>",
                        unsafe_allow_html=True,
                    )
            else:
                st.info("No FDA items match the current filters. Showing the 6 most recent overall.")
                for item in fda[:6]:
                    title = html.escape(item["title"])
                    st.markdown(
                        f"[{title}]({item['link']})  \n"
                        f"<span style='color:{GREY}; font-size:0.85em;'>{item['published']}</span>",
                        unsafe_allow_html=True,
                    )

    with reg_col_2:
        st.markdown("#### EMA news")
        with st.spinner("Fetching EMA..."):
            ema = fetch_rss(ema_url)
        if ema and ema[0].get("error"):
            st.warning(f"EMA feed unavailable: {ema[0]['error']}")
        else:
            filtered = filter_by_terms(ema, filter_terms)
            if filtered:
                st.markdown(f"<span class='stat-pill'>{len(filtered)} matching EMA items</span>",
                             unsafe_allow_html=True)
                for item in filtered[:12]:
                    title = html.escape(item["title"])
                    st.markdown(
                        f"**[{title}]({item['link']})**  \n"
                        f"<span style='color:{GREY}; font-size:0.85em;'>{item['published']}</span>",
                        unsafe_allow_html=True,
                    )
            else:
                st.info("No EMA items match the current filters. Showing the 6 most recent overall.")
                for item in ema[:6]:
                    title = html.escape(item["title"])
                    st.markdown(
                        f"[{title}]({item['link']})  \n"
                        f"<span style='color:{GREY}; font-size:0.85em;'>{item['published']}</span>",
                        unsafe_allow_html=True,
                    )

# --------------------------- Press & News tab ---------------------------
with tab_press:
    st.markdown(f"### {partner['name']} press releases and news")
    st.caption("Aggregated via Google News RSS. Two feeds: all partner news, and news scoped to our indications.")

    base_query = f'"{partner["name"]}"'
    ind_terms = " OR ".join(f'"{i}"' for i in indications) if indications else ""
    scoped_query = f'"{partner["name"]}" ({ind_terms})' if ind_terms else base_query

    news_col_1, news_col_2 = st.columns(2)
    with news_col_1:
        st.markdown("#### All partner news")
        with st.spinner("Fetching..."):
            all_news = fetch_rss(google_news_url(base_query))
        if all_news and all_news[0].get("error"):
            st.warning(f"News feed unavailable: {all_news[0]['error']}")
        else:
            st.markdown(f"<span class='stat-pill'>{len(all_news)} recent items</span>",
                         unsafe_allow_html=True)
            for item in all_news[:15]:
                title = html.escape(item["title"])
                st.markdown(
                    f"**[{title}]({item['link']})**  \n"
                    f"<span style='color:{GREY}; font-size:0.85em;'>{item['published']}</span>",
                    unsafe_allow_html=True,
                )

    with news_col_2:
        st.markdown("#### Scoped to our indications")
        if not indications:
            st.info("Select at least one indication in the sidebar to see scoped news.")
        else:
            with st.spinner("Fetching..."):
                scoped = fetch_rss(google_news_url(scoped_query))
            if scoped and scoped[0].get("error"):
                st.warning(f"News feed unavailable: {scoped[0]['error']}")
            elif not scoped:
                st.info("No indication-scoped items found. Try broadening indications.")
            else:
                st.markdown(f"<span class='stat-pill'>{len(scoped)} matching items</span>",
                             unsafe_allow_html=True)
                for item in scoped[:15]:
                    title = html.escape(item["title"])
                    st.markdown(
                        f"**[{title}]({item['link']})**  \n"
                        f"<span style='color:{GREY}; font-size:0.85em;'>{item['published']}</span>",
                        unsafe_allow_html=True,
                    )

# --------------------------- Footer ---------------------------
st.divider()
st.caption(
    "Internal Infinitopes dashboard · data pulled live from public sources · "
    "no API keys, no cost · cache TTL 30-60 min. "
    "To add or remove a partner, edit partners.yaml in the GitHub repo and redeploy."
)
