# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Daphnie Analytics Dashboard

## What this is
A Streamlit analytics dashboard for MOVEXERCISE8, an online course by Daphnie Wong (Tree Solutions). Tracks the full webinar funnel: ads → leads → webinar attendance → sales → payment completion. Diagnoses why sales rise or fall.

## Commands
- `streamlit run app.py` — start the dashboard.
- `python utils/data_loader.py` — exercise the loader in isolation; prints summary counts. Use this to debug CSV/normalization issues without spinning up Streamlit.
- `python scripts/fetch_purchases_data.py [--dry-run]` — refresh `data/purchases.csv` from the Google Sheet. Requires `PURCHASES_SHEET_URL` in `.env`.
- `python scripts/fetch_zoom_data.py --days 14` — pull recent Zoom participant CSVs into `data/zoom_participants/`. Requires `ZOOM_ACCOUNT_ID`, `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET` in `.env`. The sidebar's "Fetch new Zoom data" button invokes this same script via subprocess.
- First-time setup: `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt`.
- The Gemini API key for the AI Assistant tab is read from `.streamlit/secrets.toml` (`GEMINI_API_KEY = "..."`); the sidebar lets users override it per-session.

## Architecture
- `app.py` is the only entry point. It calls `load_all()` once, then **mutates `data` in place** based on the sidebar date filter ([app.py:69-80](app.py#L69-L80)) before dispatching to each section's `render(data)`. Section files must NOT re-apply date filters — the data they receive is already scoped.
- `load_all()` returns a dict with these keys (this shape is the contract between the loader and every section):
  - `leads` — DataFrame
  - `purchases` — DataFrame, enriched with an `inferred_webinar` column (nearest webinar on/before the purchase date, within 14 days)
  - `webinars` — **dict** keyed by session id, not a DataFrame. Each value has `date`, attendee lists, etc.
  - `meta` — DataFrame of Meta Ads rows
  - `objections` — DataFrame, includes a `_filter_date` column used by the sidebar date filter
  - `ebook` — DataFrame of e-book download survey responses (134+ rows). Phone-normalized via `normalize_phone` and age-bucketed via `parse_child_age_bucket` at load time. Pulled live from Google Sheets (5-min TTL); empty DataFrame if Sheets unavailable.
  - `config` — parsed `data/config.json`
- `utils/ai.py` wraps Gemini 2.5 Flash. AI suggestions per section and the AI Assistant tab both flow through it.
- Per-webinar sales aggregation: use `get_webinar_sales_summary()` from `utils/data_loader.py` rather than re-deriving from `purchases` + `inferred_webinar`.

## Project structure
- `app.py` — Entry point. Just sidebar + tab routing. Keep this file under 80 lines.
- `sections/` — One file per dashboard tab. Each exports a `render(data)` function.
- `utils/data_loader.py` — Loads and normalizes all CSVs. Cached with `@st.cache_data`.
- `utils/metrics.py` — Pure calculation functions. Take DataFrames, return numbers/dicts. No Streamlit calls.
- `utils/charts.py` — Reusable Plotly chart helpers with consistent styling.
- `utils/styles.py` — CSS, color constants, metric card helper, alert helper.
- `data/` — All CSVs and the `zoom_participants/` folder. Plus `config.json` for program metadata.
- `scripts/fetch_purchases_data.py` — Pulls `purchases.csv` from the public Google Sheet via CSV-export URL. Requires `PURCHASES_SHEET_URL` in `.env`. Supports `--dry-run`.
- `scripts/fetch_zoom_data.py` — Pulls Zoom participant CSVs via Server-to-Server OAuth. Requires `ZOOM_ACCOUNT_ID`, `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET` in `.env`. Uses per-occurrence UUID so same-date sessions don't collide.
- `scripts/fetch_meta_ads.py` — Pulls daily ad insights from the Meta Marketing API and overwrites `data/meta_ads.csv`. Requires `META_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID` in `.env`. Supports `--days`, `--from`/`--to`, `--dry-run`.

## Conventions
- All metric calculations live in `utils/metrics.py`. Never inline math in section files.
- All chart styling goes through helpers in `utils/charts.py`. Don't hardcode colors or layouts in section files.
- All CSS goes in `utils/styles.py`. Don't add inline `<style>` blocks elsewhere.
- Use the existing color palette from `utils/styles.py`. Don't introduce new colors without a reason.
- Section files should only contain rendering logic — they call metric functions and chart functions, then arrange them in columns.
- Use `@st.cache_data` for any function that loads or processes data.
- Keep section files focused. If a section is over 200 lines, something is being done in the wrong place.

## Data files
- `leads.csv` — Lead registrations. Columns: date, name, email, phone, utm_campaign, utm_content
- `purchases.csv` — Buyer records. Columns: date, name, email, phone, amount, status, payment_method, payment_complete, utm_campaign, utm_content, notes
- `meta_ads.csv` — Ad spend data from Meta Ads Manager export
- `objections.csv` — Failed lead analysis. Columns: name, phone, webinar_date, primary_objection, category, child_issue, child_age, notes
- `zoom_participants/*.csv` — Raw Zoom participant reports. Files with `__1_` in the name are duplicates and should be skipped.
- `config.json` — Program metadata (name, teacher, course fee, currency, offer timing)

## Important quirks
- Phone numbers come in messy formats (+60 12-345 6789, 60123456789, 0123456789). Always normalize through `normalize_phone()` in `data_loader.py` before matching.
- The purchase list has MIXED date formats: invoices 1-49 use DD/MM/YYYY, invoices 50+ use M/D/YYYY. Use `parse_purchase_date()` which handles this.
- Email matching is unreliable (only ~22% of buyers had matching emails to leads). Phone matching is much better (~95%). Always try phone first, email second.
- Zoom participant files come in pairs (one with `__1_` suffix). The duplicates have identical data — skip them.
- The "offer timing" is around 120 minutes into each Day 1 webinar. This is the key moment for engagement analysis.
- `purchases.csv` is now a **fallback cache only**. The dashboard pulls live from Google Sheets via `gspread` inside `load_purchases()` (5-min TTL, same pattern as `load_leads()`). Sheet ID and gid are in `.streamlit/secrets.toml` under `[sheets]`. The service account `sheets-reader@movexercise8.iam.gserviceaccount.com` must have view access to the sheet. `scripts/fetch_purchases_data.py` still works for manual refreshes of the local CSV but is no longer required for the dashboard to be fresh.
- `meta_ads.csv` is auto-pulled from the Meta Marketing API — do not hand-edit. Run `python scripts/fetch_meta_ads.py` to refresh. Ranking columns use literal `"-"` for missing data (the dashboard filters on this exact string).
- `load_all()` enriches purchases with an `inferred_webinar` column (nearest webinar on/before the purchase date, within 14 days). Use `get_webinar_sales_summary()` from `utils/data_loader.py` for per-webinar sales breakdowns.

## Testing
- Run locally with `streamlit run app.py`
- Test data loading independently with `python utils/data_loader.py`
- Always verify numbers against the source CSVs when adding new metrics.

## What's built
- [done] Phase 1: Overview, Sales & Revenue, Lead Pipeline, Webinar Performance
- [done] Phase 2a: Failed Leads (objection breakdown, recoverability, audience profile)
- [removed] Phase 2b: Cohort Analysis tab. The monthly cohort table + conversion-rate-by-month chart now live in the Overview tab as "Monthly Performance" (with a month-over-month delta panel). The engagement trend line moved to the Webinar Performance tab as "Engagement Over Time" with a 3-webinar rolling average. The funnel heatmap and webinar-cohort comparison were dropped (duplicated existing views). `build_monthly_cohorts`, `build_webinar_cohorts`, `build_cohort_heatmap`, `calculate_cohort_summary`, and `calculate_engagement_trend` are kept in `utils/metrics.py` for potential reuse but are currently unreferenced.
- [done] Phase 3: Ad Spend & ROI (spend overview, creative comparison, top ads, quality rankings, ROI analysis)
- [done] Phase 4: AI suggestions per section (Gemini 2.5 Flash), AI chatbot tab
- [done] E-book Survey tab — surfaces self-reported objections + intent vs actual conversion, with canonical-bucket regex matching for the free-text "What stops you from joining" column. Sheet config in `[sheets]` section of `.streamlit/secrets.toml` (`ebook_sheet_id`, `ebook_worksheet_gid`).
- [done] Purchases auto-pull from Google Sheets + webinar attribution (`inferred_webinar`, "Sales from latest" Overview card)

Update this checklist as features get added.