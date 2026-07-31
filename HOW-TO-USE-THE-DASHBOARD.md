# Your Analytics Dashboard — How to Use It

A plain-language guide to the MOVEXERCISE8 dashboard: how to open it, what each part
tells you, and where the numbers come from. No technical knowledge needed.

---

## What this dashboard is

It's a single web page that pulls together everything about your webinar sales funnel —
your ads, the leads who sign up, who shows up to the webinar, who buys, and who still owes
money — and turns it into charts and lists you can read at a glance. Instead of digging
through spreadsheets and Zoom reports, you open one link and see the whole picture.

---

## How to open it

1. Open the link you were sent (it ends in `.streamlit.app`). A bookmark it in your browser
   so you can find it again.
2. Sign in with your **Google account** — the same email address that was added for you.
   If it says you don't have access, that email hasn't been added yet; let Sorn know.
3. That's it. Nothing to install, no passwords to manage. It works on a laptop or phone,
   though it's easiest to read on a bigger screen.

> **Keep the link private.** The dashboard shows real customer names, phone numbers, and
> payment details, so please don't forward the link or share your login.

---

## The layout

The page has two parts:

- **The sidebar (left)** — a date filter, some data counts, and a "Data freshness" panel.
- **The tabs (top)** — ten tabs, each answering a different business question. Click a tab
  to switch views.

If the sidebar is hidden, click the little **`>`** arrow in the top-left to open it.

---

## The tabs, and what each one is for

You don't need all ten every day. Here's what each answers, roughly in order of how often
you'll want it:

- **Overview** — the health check. Are things up or down this month versus last? Start here.
- **Sales & Revenue** — the money view. How much came in, how much was collected, and how
  much is still outstanding.
- **Hot List** — your call list. Warm leads who came to the webinar but haven't bought yet,
  ranked by how likely they are to buy. This is who to follow up with first.
- **Payments Due** — who owes money this month on their installment plan, so nobody slips
  through. You can optionally upload a Stripe export here to tick off who's already paid.
- **Lead Pipeline** — where leads come from and how they move from signup to purchase.
- **Webinar Performance** — how each webinar did: attendance, drop-off, and engagement
  around the offer moment.
- **Failed Leads** — why people *didn't* buy, grouped by objection (price, timing, spouse
  buy-in, etc.), so you can spot patterns.
- **E-book Survey** — what people who downloaded the e-book said about their goals and what's
  holding them back.
- **Ad Spend & ROI** — what you're spending on ads and what it's returning, ad by ad.
- **AI Assistant** — see below; this is your shortcut.

### The AI Assistant is your shortcut

If you don't want to hunt through tabs, go to the **AI Assistant** tab and just type a
question in plain English — for example:

- *"Why did sales drop last month?"*
- *"Who are the top 5 people I should call this week?"*
- *"Which ad is performing best right now?"*

It reads the same data the charts use and answers in a sentence or two. It already has
everything it needs to work — you don't have to set anything up.

---

## Using the date filter

In the sidebar, **Date Filter** lets you narrow everything to a specific stretch of time —
say, just last month. Every tab updates to match. To go back to everything, widen the range
to the full span again. (Two tabs — **Hot List** and **Payments Due** — always look at *all*
your data on purpose, because they're action lists for right now.)

---

## Is the data up to date?

Yes — it updates on its own. But if you want to check:

- The **Data freshness** panel in the sidebar shows the most recent piece of data from each
  source (e.g. *"Purchases — Jul 30 (1 day ago)"*).
- If you ever see a **⚠️** next to a source, it means that feed hasn't updated in a while and
  something may need attention — tell Sorn.
- There's also a **Refresh data** button in the sidebar if you want to force a reload; you
  normally won't need it.

---

## Where the numbers come from (what's connected)

You don't have to manage any of this — it's wired up behind the scenes — but here's what
feeds the dashboard, so you know the numbers are real:

- **Google Sheets** — your leads, purchases, and e-book survey responses come straight from
  your Google Sheets, refreshed every few minutes. When your team updates the sheet, the
  dashboard follows automatically.
- **Zoom** — webinar attendance (who showed up, how long they stayed) comes from your Zoom
  account's participant reports.
- **Meta Ads (Facebook/Instagram)** — ad spend, reach, and results come from your Meta Ads
  account, including the ad images.
- **Stripe** *(optional)* — on the Payments Due tab you can upload a Stripe export to match
  payments against who owes money.
- **WhatsApp follow-ups** — the "why they didn't buy" analysis on the Failed Leads tab is
  entered by your team from customer conversations.

Once a day, overnight, the dashboard automatically pulls the latest from Zoom and Meta and
refreshes itself, so by morning everything's current.

---

## If something looks off

- A number seems wrong, a chart is empty, or the page shows an error → **tell Sorn.** You
  can't break anything by clicking around, so explore freely — but fixes are on the tech side.
- You can always screenshot a chart or table to drop into a message or report.

---

*Questions about how to *use* it: this guide, then Sorn. Questions about how it's *built*:
that's in the repo's `README.md` and `CLAUDE.md`, for the technical side.*
