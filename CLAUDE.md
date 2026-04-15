# Daphnie Analytics Dashboard

## What this is
A Streamlit analytics dashboard for MOVEXERCISE8, an online course by Daphnie Wong (Tree Solutions). Tracks the full webinar funnel: ads → leads → webinar attendance → sales → payment completion. Diagnoses why sales rise or fall.

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
- `purchases.csv` is auto-pulled from Google Sheets — do not hand-edit. Run `python scripts/fetch_purchases_data.py` to refresh.
- `load_all()` enriches purchases with an `inferred_webinar` column (nearest webinar on/before the purchase date, within 14 days). Use `get_webinar_sales_summary()` from `utils/data_loader.py` for per-webinar sales breakdowns.

## Testing
- Run locally with `streamlit run app.py`
- Test data loading independently with `python utils/data_loader.py`
- Always verify numbers against the source CSVs when adding new metrics.

## What's built
- [done] Phase 1: Overview, Sales & Revenue, Lead Pipeline, Webinar Performance
- [done] Phase 2a: Failed Leads (objection breakdown, recoverability, audience profile)
- [done] Phase 2b: Cohort Analysis (monthly cohorts, webinar cohort comparison, funnel heatmap)
- [done] Phase 3: Ad Spend & ROI (spend overview, creative comparison, top ads, quality rankings, ROI analysis)
- [done] Phase 4: AI suggestions per section (Gemini 2.5 Flash), AI chatbot tab
- [done] Purchases auto-pull from Google Sheets + webinar attribution (`inferred_webinar`, "Sales from latest" Overview card)

Update this checklist as features get added.