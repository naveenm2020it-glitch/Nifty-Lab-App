# NIFTY Seller Intelligence — implementation notes

## Scope
Personal-use research module for the existing NIFTY LAB web + Capacitor Android application.

## Data contract
The analysis endpoint accepts a CSV with one row per option contract per timestamp/session. Required columns (aliases are accepted): trade_date, expiry, strike, option_type (CE/PE), oi, change_oi, volume, ltp, spot. Optional: snapshot_time.

## Analysis
- Exact-expiry filtering prevents silently mixing different expiry contracts.
- 5-session and 22-session comparisons show the available coverage for the selected expiry.
- CE clusters above/at spot and PE clusters below/at spot are candidates only.
- Candidate ranking combines relative OI, positive OI change, volume rank and premium weakness.
- Intraday possible short-covering pressure is flagged only when timestamped rows show premium expansion, OI contraction and volume expansion together.

## Important limitations
Public OI is matched open interest, not a seller-specific position ledger. It cannot reveal individual seller entry premium or prove panic exit. EOD data can rank defence candidates; intraday snapshots are required to study repeatable exit-pressure premium zones. The engine deliberately returns a null panic premium threshold until sufficient intraday history exists.

## Automatic data collection
Do not scrape NSE website pages or undocumented endpoints. Set MARKET_DATA_PROVIDER and MARKET_DATA_API_KEY only after selecting an authorised/licensed provider and confirming its API rights cover personal app use, storage and historical replay. The collector integration is intentionally disabled until provider credentials and endpoint contract are supplied.

## Deployment notes
The current Render workspace has no managed Postgres instance. Do not deploy persistent automated collection to an ephemeral filesystem. Provision Postgres (and an appropriate worker/cron schedule) only after the user reviews the plan and accepts any cost. Keep API credentials in Render environment variables, never in source control.
