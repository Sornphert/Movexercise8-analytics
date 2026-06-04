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
- `app.py` is the only entry point. It calls `load_all()` once, then **mutates `data` in place** based on the sidebar date filter ([app.py:69-84](app.py#L69-L84)) before dispatching to each section's `render(data)`. Section files must NOT re-apply date filters — the data they receive is already scoped. The filter scopes `leads`, `purchases`, `objections` (rows with no `_filter_date` are kept), `webinars`, and `ebook`.
- **Two tabs deliberately bypass the sidebar filter**: `sections/hot_list.py` and `sections/payments_due.py` re-call `load_all()` to get the unfiltered (cached) data. These are operational worklists (who to call, who owes money this month) that must reason over the entire dataset regardless of the selected date range. Do not "fix" this by switching them to the passed-in `data`.
- `load_all()` returns a dict with these keys (this shape is the contract between the loader and every section):
  - `leads` — DataFrame, enriched with a `registered_for_webinar` column (next webinar within 9 days of registration, or 'Unknown') and a `converted` boolean column (lead matched a purchase on normalized email or phone)
  - `purchases` — DataFrame, enriched with an `inferred_webinar` column (nearest webinar on/before the purchase date, within 14 days)
  - `webinars` — **dict** keyed by session id, not a DataFrame. Each value has `date`, attendee lists, etc.
  - `meta` — DataFrame of Meta Ads rows
  - `ad_attribution` — DataFrame matching ad creatives to attributed buyers/revenue via utm_content
  - `ad_creatives` — DataFrame with image paths for currently-active ads. May be empty if `scripts/fetch_meta_ads.py --creatives` hasn't been run.
  - `objections` — DataFrame, includes a `_filter_date` column used by the sidebar date filter
  - `ebook` — DataFrame of e-book download survey responses (134+ rows). Phone-normalized via `normalize_phone` and age-bucketed via `parse_child_age_bucket` at load time. Pulled live from Google Sheets (5-min TTL); empty DataFrame if Sheets unavailable.
  - `config` — parsed `data/config.json`
- `utils/ai.py` wraps Gemini 2.5 Flash. AI suggestions per section and the AI Assistant tab both flow through it.
- Per-webinar sales aggregation: use `get_webinar_sales_summary()` from `utils/data_loader.py` rather than re-deriving from `purchases` + `inferred_webinar`.

## Project structure
- `app.py` — Entry point. Sidebar (Refresh data / Fetch new Zoom data buttons, date filter, data-loaded counts) + 10-tab routing. Keep this file lean (~125 lines).
- `sections/` — One file per dashboard tab. Each exports a `render(data)` function. The 10 tabs, in order: `overview`, `sales_revenue`, `lead_pipeline`, `webinar_performance`, `failed_leads`, `hot_list`, `payments_due`, `ebook_survey`, `ad_spend_roi`, `ai_chat`.
- `utils/data_loader.py` — Loads and normalizes all CSVs. Cached with `@st.cache_data`.
- `utils/metrics.py` — Pure calculation functions. Take DataFrames, return numbers/dicts. No Streamlit calls.
- `utils/charts.py` — Reusable Plotly chart helpers with consistent styling.
- `utils/styles.py` — CSS, color constants, metric card helper, alert helper.
- `data/` — All CSVs and the `zoom_participants/` folder. Plus `config.json` for program metadata.
- `scripts/fetch_purchases_data.py` — Pulls `purchases.csv` from the public Google Sheet via CSV-export URL. Requires `PURCHASES_SHEET_URL` in `.env`. Supports `--dry-run`.
- `scripts/fetch_zoom_data.py` — Pulls Zoom participant CSVs via Server-to-Server OAuth. Requires `ZOOM_ACCOUNT_ID`, `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET` in `.env`. Uses per-occurrence UUID so same-date sessions don't collide.
- `scripts/fetch_meta_ads.py` — Pulls daily ad insights from the Meta Marketing API and **merges** the fetched window into `data/meta_ads.csv` (dates outside the window are preserved; rows are de-duped on `(reporting_starts, ad_name)` with fetched data winning, then sorted by date). Large windows are fetched in 30-day chunks internally to avoid Meta's HTTP 500. Requires `META_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID` in `.env`. Supports `--days`, `--from`/`--to`, `--dry-run`, `--overwrite` (wipe + write window only), `--backfill`, `--creatives` (also fetches image cache for active ads).
- `scripts/recategorize_still_considering.py` — One-off maintenance script that re-buckets vague "still considering" rows in `objections.csv` into more specific objection categories.

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
- `meta_ad_creatives.csv` — Metadata for cached ad images. Auto-pulled with `scripts/fetch_meta_ads.py --creatives`. Active ads only.
- `ad_creatives/*.jpg` — Cached creative images (one per active ad), keyed by Meta ad_id. Re-downloaded when older than 7 days.
- `objections.csv` — Failed lead analysis. Columns: name, phone, webinar_date, primary_objection, category, child_issue, child_age, notes
- `zoom_participants/*.csv` — Raw Zoom participant reports. Files with `__1_` in the name are duplicates and should be skipped.
- `email_aliases.csv` — Staff-maintained `stripe_email,buyer_email` mapping. Used by the Payments Due tab to match Stripe charges to buyers whose Stripe email differs from their purchase-sheet email. Loaded via `load_email_aliases()`.
- `config.json` — Program metadata: `program_name`, `teacher_name`, `course_fee_full` (2688), `currency` (MYR), `webinar_format`, `offer_timing_minutes` (120), `webinar_scheduled_start`.

## Important quirks
- Phone numbers come in messy formats (+60 12-345 6789, 60123456789, 0123456789). Always normalize through `normalize_phone()` in `data_loader.py` before matching.
- The purchase list has MIXED date formats: invoices 1-49 use DD/MM/YYYY, invoices 50+ use M/D/YYYY. Use `parse_purchase_date()` which handles this.
- Email matching is unreliable (only ~22% of buyers had matching emails to leads). Phone matching is much better (~95%). Always try phone first, email second.
- Zoom participant files come in pairs (one with `__1_` suffix). The duplicates have identical data — skip them.
- The "offer timing" is around 120 minutes into each Day 1 webinar. This is the key moment for engagement analysis.
- `purchases.csv` is now a **fallback cache only**. The dashboard pulls live from Google Sheets via `gspread` inside `load_purchases()` (5-min TTL, same pattern as `load_leads()`). Sheet ID and gid are in `.streamlit/secrets.toml` under `[sheets]`. The service account `sheets-reader@movexercise8.iam.gserviceaccount.com` must have view access to the sheet. `scripts/fetch_purchases_data.py` still works for manual refreshes of the local CSV but is no longer required for the dashboard to be fresh.
- `meta_ads.csv` is auto-pulled from the Meta Marketing API — do not hand-edit. Run `python scripts/fetch_meta_ads.py` to refresh; this **merges** the fetched window into the file (history outside the window is kept). Use `--overwrite` only if you intentionally want to discard everything but the fetched window. Ranking columns use literal `"-"` for missing data (the dashboard filters on this exact string).
- `load_all()` enriches purchases with an `inferred_webinar` column (nearest webinar on/before the purchase date, within 14 days). Use `get_webinar_sales_summary()` from `utils/data_loader.py` for per-webinar sales breakdowns.
- `load_all()` enriches leads with a `registered_for_webinar` column (next webinar within 9 days). Use `get_webinar_registration_summary()` from `utils/data_loader.py` for per-webinar registration breakdowns. The 9-day window covers ad campaigns that run between Mon-Thu webinar dates.
- Ad-to-buyer attribution requires `utm_content` on `purchases.csv` to match `ad_name` in `meta_ads.csv`. Coverage is partial (~80% of buyers have UTMs). Ads with `buyers=0` in `data["ad_attribution"]` may have actual buyers we couldn't attribute via UTM.
- Ad creative images are cached locally in `data/ad_creatives/` only for currently-active ads. Run `python scripts/fetch_meta_ads.py --creatives` to refresh. Paused ads won't have previews — that's intentional to keep the cache lean.
- **Payments Due** (`calculate_payments_due`) infers an installment schedule from signup date: one row per installment buyer still within their plan window (months 1..plan_length). The current month's installment is treated as still *due* (the payment being chased), so a buyer in their final month surfaces as "Final month" rather than dropping out. Buyers past their final month, refunds, and buyers who paid full upfront despite an "Installment" label are excluded. This is a schedule, not a record of confirmed-unpaid — a buyer may have already paid or paid early.
- **Stripe reconciliation** (`reconcile_payments_with_stripe`) is optional: upload a Stripe export CSV (must have `Customer Email`, `Status`, `Amount`, `Description`) on the Payments Due tab to tag each due buyer Paid / Failed / No record. Matching order: email → `email_aliases.csv` alias → exact name-in-email fallback. Stripe charges that match no due buyer are listed separately for manual resolution.
- **Hot List** (`calculate_hot_list`) ranks warm non-buyer leads by buying signals (stayed to the offer pitch, high stated intent from the e-book survey, a logged objection, recent attendance). It excludes anyone who has purchased across the *entire* purchase set, which is why it (like Payments Due) re-loads unfiltered data.

## Testing
- Run locally with `streamlit run app.py`
- Test data loading independently with `python utils/data_loader.py`
- Always verify numbers against the source CSVs when adding new metrics.

## What's built
- [done] Phase 1: Overview, Sales & Revenue, Lead Pipeline (rebuilt with funnel-health, show-up diagnosis, lead-source quality, time-to-convert), Webinar Performance
- [done] Phase 2a: Failed Leads (objection breakdown, recoverability, audience profile)
- [removed] Phase 2b: Cohort Analysis tab. The monthly cohort table + conversion-rate-by-month chart now live in the Overview tab as "Monthly Performance" (with a month-over-month delta panel). The engagement trend line moved to the Webinar Performance tab as "Engagement Over Time" with a 3-webinar rolling average. The funnel heatmap and webinar-cohort comparison were dropped (duplicated existing views). `build_monthly_cohorts`, `build_webinar_cohorts`, `build_cohort_heatmap`, `calculate_cohort_summary`, and `calculate_engagement_trend` are kept in `utils/metrics.py` for potential reuse but are currently unreferenced.
- [done] Phase 3: Ad Spend & ROI (rebuilt with snapshot, trend, decision panels, creative type, campaign performance, fatigue tracker, top ads, quality rankings, ROI analysis)
- [done] Phase 4: AI suggestions per section (Gemini 2.5 Flash), AI chatbot tab
- [done] E-book Survey tab — surfaces self-reported objections + intent vs actual conversion, with canonical-bucket regex matching for the free-text "What stops you from joining" column. Sheet config in `[sheets]` section of `.streamlit/secrets.toml` (`ebook_sheet_id`, `ebook_worksheet_gid`).
- [done] Purchases auto-pull from Google Sheets + webinar attribution (`inferred_webinar`, "Sales from latest" Overview card)
- [done] Ad creative preview — pick an ad in Top Ads or Decision Panels to view its image. Active ads only; opt-in via `scripts/fetch_meta_ads.py --creatives`.
- [done] Hot List tab — warm non-buyer leads scored by buying signals (offer-pitch attendance, stated intent, logged objection, recency) as a top-down call list. Reasons over the full unfiltered dataset.
- [done] Payments Due tab — monthly installment collection worklist inferred from signup dates, ranked by total outstanding. Optional Stripe-export upload reconciles the schedule against actual Paid/Failed charges (email → alias table → name-in-email matching). Reasons over the full unfiltered dataset.

Update this checklist as features get added.