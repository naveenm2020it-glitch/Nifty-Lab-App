# NIFTY Seller Intelligence

Seller Intelligence is a research module added to NIFTY LAB.

## Current capabilities
- Exact-expiry option-chain analysis from CSV.
- Five-session vs 22-session OI and premium comparison.
- Candidate CE resistance and PE support clusters.
- Possible short-covering pressure events when timestamped intraday snapshots are supplied.
- Explicit data coverage and limitation reporting.

## CSV format
Required fields: trade_date, expiry, strike, option_type, oi, change_oi, volume, ltp, spot.
Optional field: snapshot_time (for intraday event analysis).

## API
- GET /api/seller-intelligence/status
- POST /api/seller-intelligence/analyze-csv?expiry=YYYY-MM-DD

## Automatic data
Automatic collection is deliberately not enabled until an authorised market-data vendor/API and credentials are configured. Do not use automated scraping of NSE webpages or undocumented endpoints. The app must not invent seller entry premiums or panic-exit levels.

See SELLER_INTELLIGENCE_SPEC.md for design details.
