# Infinitopes Partner Intelligence Dashboard

Live monitoring dashboard for Tier 1-2 pharma partners. Reads directly from
free public data sources — no API keys, no accounts, no ongoing cost.

## Data sources

| Source | What it gives us | Free? |
|---|---|---|
| ClinicalTrials.gov API v2 | Every trial per partner in our indications, in real time | Yes |
| SEC EDGAR | 10-K, 10-Q, 8-K, 20-F, 6-K filings for US-listed partners | Yes |
| FDA press announcements RSS | US regulatory news (approvals, warnings, guidance) | Yes |
| EMA news RSS | European regulatory news | Yes |
| Google News RSS | Company press releases and general news | Yes |

## What the dashboard looks like

A single page with a partner picker in the sidebar and four tabs:

1. **Clinical trials** — All matching studies for the selected partner,
   sorted by most recently updated, filtered by the indication terms you
   pick in the sidebar. Shows NCT ID, phase, status, conditions, last-update
   date, and a direct link.
2. **SEC filings** — Recent regulatory filings (for US-listed partners only).
   Direct links to each filing.
3. **FDA / EMA** — Both regulators' latest announcements, filtered to
   mentions of the partner or our indications.
4. **Press & news** — Google News aggregation, one column for all partner
   news, one column scoped to our indications.

Everything is cached for 30-60 minutes to avoid hammering the APIs.
The sidebar has a "Refresh all data" button that forces a live pull.

## To deploy (about 30 minutes, one-time)

You need two accounts: **GitHub** (free) and **Streamlit Community Cloud**
(free, signs in with GitHub). No other services or payments needed.

### Step 1: Create a GitHub repo

1. Go to [github.com](https://github.com) and sign in, or create a free
   account. Any personal or Infinitopes-branded account will do.
2. Click the green **New** button (or go to
   [github.com/new](https://github.com/new)).
3. Repository name: something like `partner-intelligence`.
4. Description: something like "Infinitopes internal partner monitoring
   dashboard."
5. Set to **Private** (keeps the source visible only to you, but the
   deployed app can still be publicly viewable — Streamlit is separate).
6. Tick **Add a README file** (this creates the repo so you can upload to it).
7. Click **Create repository**.

### Step 2: Upload the four files

In the new repo, click **Add file → Upload files** (top right of the file
list). Drag and drop these four files:

- `app.py`
- `partners.yaml`
- `requirements.txt`
- `README.md` (this file)

Then scroll down and click **Commit changes**.

### Step 3: Deploy on Streamlit Community Cloud

1. Go to [streamlit.io/cloud](https://streamlit.io/cloud) and click
   **Sign in with GitHub**. Grant access when prompted — Streamlit needs to
   see your repos.
2. Click **Create app**, then **Deploy a public app from GitHub**.
3. Choose the repo you just created.
4. Branch: `main`. Main file path: `app.py`.
5. App URL: leave the default or customise the subdomain — this becomes the
   URL you share, e.g. `infinitopes-partner-intel.streamlit.app`.
6. Click **Deploy**.

Streamlit will install the Python dependencies (takes 1-3 minutes) and
launch the app. When it's ready, the URL is what you send to the team.
Anyone with the link can view it — no sign-in required.

### Step 4: Share the URL

Send the Streamlit URL to Tom, Dan, Jonathan, Phillipa, or whoever needs it.
It works on desktop and mobile. No credentials needed on their end.

## To add, remove, or edit a partner

Edit `partners.yaml` directly on GitHub (there's a pencil icon at the top
right of the file view). Follow the template. Fields:

| Field | Required? | Notes |
|---|---|---|
| `name` | Yes | Displayed in the sidebar and header |
| `ticker` | No | Displayed as a metric |
| `cik` | No | SEC ID; leave `""` for non-US-listed. See below. |
| `hq` | No | Displayed as a metric |
| `focus` | No | Free-text — e.g. "Durvalumab / oncology backbone" |
| `our_contact` | No | Our BD contact at that company |
| `tier` | No | T1 / T2 / T3 |
| `website` | Yes | External link on the header |

After committing changes, Streamlit auto-redeploys in about a minute.

### Finding a SEC CIK number

Go to
[www.sec.gov/cgi-bin/browse-edgar?action=getcompany](https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany),
search for the partner, and copy the CIK number from the results. Enter it
as a string in `partners.yaml` (e.g. `cik: "901832"` for AstraZeneca).

Leave `cik` as `""` for partners that don't file with the SEC — the app
shows a friendly "not applicable" note instead of a broken tab. This is
the case for:

- Merck KGaA (Darmstadt) — files with BaFin in Germany, not the SEC
- Roche (Basel) — Swiss disclosure regime
- Kyowa Kirin (Tokyo) — JPX disclosure

For those partners, the Press & News tab is the main information channel.

## Editing the indication list

The `default_indications` list at the top of `partners.yaml` controls the
sidebar filter options. Add or remove terms to reflect our current focus.
Applies to the ClinicalTrials.gov query and to the scoped news feed.

## Known limitations

- **Google News RSS occasionally rate-limits** if the same viewer opens the
  page dozens of times in an hour. If a tab shows an error, wait 5 minutes
  and refresh.
- **EMA and FDA RSS URLs occasionally change.** If either the FDA or EMA
  panel shows a feed error, check the current URL on their site and update
  the constant in `app.py` (near the top of the FDA / EMA tab section).
- **Streamlit Community Cloud sleeps public apps after a week of no traffic.**
  First visitor after that gets a 30-second cold start. Send a link once a
  week to keep it warm, or upgrade to a paid tier if it becomes annoying.

## Cost

Zero. Streamlit Community Cloud is free for unlimited public apps.
GitHub is free for public and private repos.

## Roadmap (if we want a v2 later)

- LLM-summarised earnings-call transcripts (needs an Anthropic API key in
  Streamlit secrets, minor added cost)
- Historical trending charts (trials started per quarter, R&D spend over
  time)
- Custom watchlists per user
- Slack alerts on new filings or indication-relevant press releases
- Multi-partner comparison view (e.g. AZ vs Merck oesophageal trial count
  side by side)

Say when you want any of these, and I'll add them.
