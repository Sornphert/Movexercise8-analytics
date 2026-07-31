# Movexercise8 Analytics

A **Streamlit** analytics dashboard for MOVEXERCISE8 (Tree Solutions). It tracks the full
webinar sales funnel — ads → leads → webinar attendance → sales → payment completion — and
helps diagnose why sales rise or fall.

> ⚠️ **Private repo — keep it private.** The `data/` folder contains real customer PII
> (names, emails, phone numbers, purchase amounts). This repository must never be made
> public.

## What's inside

- **`app.py`** — the entry point; loads all data once and renders the dashboard tabs.
- **`sections/`** — one file per dashboard tab (overview, sales & revenue, lead pipeline,
  webinar performance, failed leads, hot list, payments due, e-book survey, ad spend & ROI,
  AI assistant).
- **`utils/`** — data loading, metrics, charts, styling, and the AI helper.
- **`scripts/`** — pull fresh data from Zoom, Meta Ads, and Google Sheets.
- **`data/`** — the CSVs the dashboard reads (leads, purchases, Meta ads, objections, Zoom
  participants, config).

Deeper architecture and conventions are documented in **`CLAUDE.md`**.

## Prerequisites

- **Python 3.10+**

## Setup

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Secrets

The dashboard reads keys from **`.streamlit/secrets.toml`** (git-ignored). The data-fetch
scripts read from a **`.env`** file (git-ignored) — copy `.env.example` to `.env` and fill
it in.

Keys used:

- **Gemini** (`GEMINI_API_KEY`) — for the AI Assistant tab.
- **Google Sheets** (`gcp_service_account` + sheet IDs) — live source for leads / purchases
  / e-book survey. If not configured, the app falls back to the committed CSVs.
- **Zoom** (`ZOOM_ACCOUNT_ID`, `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET`) — for the
  fetch-Zoom-data script.
- **Meta Ads** (`META_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID`) — for the fetch-ads script.

Get the real values from the project owner (share them securely, never commit them).

## Run

```bash
streamlit run app.py              # opens the dashboard in your browser
```

Quick data-loader check without launching the UI:

```bash
python utils/data_loader.py       # prints row counts + a summary
```

## Refreshing data

The dashboard reads data from `data/`. To pull fresh data:

```bash
python scripts/fetch_purchases_data.py [--dry-run]   # purchases from Google Sheet
python scripts/fetch_zoom_data.py --days 14          # recent Zoom participants
python scripts/fetch_meta_ads.py [--creatives]       # Meta ad stats (+ creative images)
```

The sidebar's **"Fetch new Zoom data"** button runs the Zoom script for you.

## Deployment

Hosted on **Streamlit Community Cloud**, deployed from the `main` branch of this repo.
Secrets are configured in the Streamlit Cloud app settings (not in the repo).
