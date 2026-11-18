"""HTTP endpoints for NIFTY Seller Intelligence research."""
from __future__ import annotations

import os
import hmac
from io import BytesIO

import pandas as pd
from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile

from app.seller_intelligence import analyze_option_chain

router = APIRouter(prefix="/api/seller-intelligence", tags=["Seller Intelligence"])


@router.get("/status")
def seller_intelligence_status():
    provider = os.getenv("MARKET_DATA_PROVIDER", "").strip().lower()
    configured = bool(provider and os.getenv("MARKET_DATA_API_KEY"))
    return {
        "module": "NIFTY Seller Intelligence",
        "analysis_engine": "available",
        "automatic_collection": "configured" if configured else "awaiting_licensed_market_data_credentials",
        "provider": provider or None,
        "required_environment": ["MARKET_DATA_PROVIDER", "MARKET_DATA_API_KEY"],
        "note": "No NSE website scraping is performed by this module. Configure an authorised market-data API/feed before enabling unattended collection.",
    }


@router.post("/analyze-csv")
async def analyze_seller_csv(
    file: UploadFile = File(...),
    expiry: str | None = Query(default=None, description="Optional expiry in YYYY-MM-DD format"),
    x_seller_key: str | None = Header(default=None),
):
    expected_key = os.getenv("SELLER_INTELLIGENCE_API_KEY", "")
    if not expected_key:
        raise HTTPException(status_code=503, detail="Set SELLER_INTELLIGENCE_API_KEY on the server before enabling personal data uploads.")
    if not x_seller_key or not hmac.compare_digest(x_seller_key, expected_key):
        raise HTTPException(status_code=401, detail="Invalid or missing personal app key.")

    if not file.filename or not file.filename.lower().endswith((".csv", ".txt")):
        raise HTTPException(status_code=400, detail="Upload a CSV file.")
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    try:
        frame = pd.read_csv(BytesIO(payload))
        return analyze_option_chain(frame, expiry=expiry)
    except (ValueError, pd.errors.ParserError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {type(exc).__name__}: {exc}") from exc
