"""Research-only NIFTY options seller-pressure analytics.

Important: OI is matched long/short open interest, not a seller ledger. The
engine labels candidates and observed short-covering-like conditions; it never
claims to know an individual participant's entry price or panic threshold.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

ALIASES = {
    "trade_date": ("trade_date", "date", "timestamp"),
    "expiry": ("expiry", "expiry_date", "expirydate"),
    "strike": ("strike", "strike_price", "strikeprice"),
    "option_type": ("option_type", "optiontype", "type", "right"),
    "oi": ("oi", "open_interest", "openinterest"),
    "change_oi": ("change_oi", "change_in_oi", "changeinoi", "oi_change"),
    "volume": ("volume", "traded_volume", "contracts_traded"),
    "ltp": ("ltp", "last_price", "close", "lastprice"),
    "spot": ("spot", "underlying", "underlying_value", "underlyingvalue", "spot_close"),
    "snapshot_time": ("snapshot_time", "time", "datetime"),
}


def _normalise_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    lookup = {str(c).strip().lower().replace(" ", "_"): c for c in out.columns}
    rename = {}
    for canonical, aliases in ALIASES.items():
        for alias in aliases:
            if alias in lookup:
                rename[lookup[alias]] = canonical
                break
    out = out.rename(columns=rename)
    required = ("trade_date", "expiry", "strike", "option_type", "oi", "change_oi", "volume", "ltp", "spot")
    missing = [name for name in required if name not in out.columns]
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
    out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce").dt.date
    out["expiry"] = pd.to_datetime(out["expiry"], errors="coerce").dt.date
    out["option_type"] = out["option_type"].astype(str).str.upper().str.strip()
    out = out[out["option_type"].isin(["CE", "PE"])].copy()
    for col in ("strike", "oi", "change_oi", "volume", "ltp", "spot"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["trade_date", "expiry", "strike", "oi", "volume", "ltp", "spot"])
    if out.empty:
        raise ValueError("No valid NIFTY CE/PE rows found after validation.")
    out["trade_date"] = pd.to_datetime(out["trade_date"])
    out["expiry"] = pd.to_datetime(out["expiry"])
    if "snapshot_time" in out.columns:
        out["snapshot_time"] = pd.to_datetime(out["snapshot_time"], errors="coerce")
    return out.sort_values(["trade_date", "expiry", "strike", "option_type"])


def _percentile_rank(series: pd.Series) -> pd.Series:
    if len(series) <= 1:
        return pd.Series([100.0] * len(series), index=series.index)
    return series.rank(pct=True).fillna(0) * 100


def _cluster_rows(rows: pd.DataFrame, side: str, spot: float, strike_step: float) -> list[dict[str, Any]]:
    if rows.empty:
        return []
    side_rows = rows.copy()
    # Only show the side of the chain that is structurally relevant to spot.
    side_rows = side_rows[(side_rows["strike"] >= spot) if side == "CE" else (side_rows["strike"] <= spot)]
    if side_rows.empty:
        return []
    oi_cut = side_rows["oi"].quantile(0.70)
    active = side_rows[(side_rows["oi"] >= oi_cut) & (side_rows["change_oi"] > 0)].sort_values("strike")
    if active.empty:
        return []
    groups: list[list[dict[str, Any]]] = []
    for row in active.to_dict("records"):
        if not groups or row["strike"] - groups[-1][-1]["strike"] > strike_step * 1.01:
            groups.append([row])
        else:
            groups[-1].append(row)
    result = []
    for group in groups:
        strikes = [float(r["strike"]) for r in group]
        total_oi = int(sum(r["oi"] for r in group))
        total_change = int(sum(r["change_oi"] for r in group))
        result.append({
            "side": side,
            "from_strike": min(strikes),
            "to_strike": max(strikes),
            "strikes": strikes,
            "total_oi": total_oi,
            "net_change_oi": total_change,
            "classification": "potential_call_resistance_cluster" if side == "CE" else "potential_put_support_cluster",
            "evidence": "high relative OI plus positive change in OI; confirm with spot rejection and premium behaviour",
        })
    return sorted(result, key=lambda x: (x["total_oi"], x["net_change_oi"]), reverse=True)


def _side_snapshot(latest: pd.DataFrame, previous: pd.DataFrame, side: str, spot: float) -> list[dict[str, Any]]:
    cur = latest[latest["option_type"] == side].copy()
    prev = previous[previous["option_type"] == side][["strike", "ltp", "oi"]].rename(
        columns={"ltp": "prev_ltp", "oi": "prev_oi"}
    )
    cur = cur.merge(prev, on="strike", how="left")
    cur["premium_change_pct"] = np.where(
        cur["prev_ltp"].notna() & (cur["prev_ltp"] != 0),
        (cur["ltp"] / cur["prev_ltp"] - 1) * 100, np.nan
    )
    cur["oi_change_pct"] = np.where(
        cur["prev_oi"].notna() & (cur["prev_oi"] != 0),
        (cur["oi"] / cur["prev_oi"] - 1) * 100, np.nan
    )
    cur["oi_rank"] = _percentile_rank(cur["oi"])
    cur["build_rank"] = _percentile_rank(cur["change_oi"].clip(lower=0))
    cur["volume_rank"] = _percentile_rank(cur["volume"])
    # A heuristic candidate score, not a probability or a claim about participant identity.
    premium_weakness = (-cur["premium_change_pct"].fillna(0)).clip(lower=0).clip(upper=20) / 20 * 15
    cur["candidate_score"] = (
        cur["oi_rank"] * 0.35
        + cur["build_rank"] * 0.35
        + cur["volume_rank"] * 0.15
        + premium_weakness
    ).round(1)
    cur["spot_distance"] = (cur["strike"] - spot).abs()
    cur["spot_relation"] = np.where(cur["strike"] >= spot, "above_or_at_spot", "below_spot")
    if side == "CE":
        cur["relevance"] = np.where(cur["strike"] >= spot, "overhead_candidate", "in_the_money_context")
    else:
        cur["relevance"] = np.where(cur["strike"] <= spot, "underlying_support_candidate", "out_of_the_money_context")
    records = cur.sort_values(["candidate_score", "oi"], ascending=False).head(12)
    return records[[
        "strike", "oi", "change_oi", "volume", "ltp", "premium_change_pct",
        "oi_change_pct", "candidate_score", "spot_distance", "relevance"
    ]].replace({np.nan: None}).to_dict("records")


def _window_metrics(history: pd.DataFrame, days: int) -> dict[str, Any]:
    sessions = sorted(history["trade_date"].dropna().unique())
    chosen = sessions[-days:]
    window = history[history["trade_date"].isin(chosen)]
    if window.empty:
        return {"requested_sessions": days, "available_sessions": 0, "strikes": []}
    first_day, last_day = chosen[0], chosen[-1]
    first = window[window["trade_date"] == first_day].set_index(["strike", "option_type"])
    last = window[window["trade_date"] == last_day].set_index(["strike", "option_type"])
    common = first.index.intersection(last.index)
    rows = []
    for key in common:
        a, b = first.loc[key], last.loc[key]
        rows.append({
            "strike": float(key[0]),
            "side": str(key[1]),
            "start_oi": int(a["oi"]),
            "end_oi": int(b["oi"]),
            "oi_delta": int(b["oi"] - a["oi"]),
            "start_ltp": float(a["ltp"]),
            "end_ltp": float(b["ltp"]),
            "premium_change_pct": round((float(b["ltp"]) / float(a["ltp"]) - 1) * 100, 2) if float(a["ltp"]) else None,
            "positive_oi_build_sessions": int((window[(window["strike"] == key[0]) & (window["option_type"] == key[1])]["change_oi"] > 0).sum()),
        })
    return {
        "requested_sessions": days,
        "available_sessions": len(chosen),
        "from": str(pd.Timestamp(first_day).date()),
        "to": str(pd.Timestamp(last_day).date()),
        "strikes": rows,
        "coverage_note": "30-session analysis uses only sessions available for this exact expiry; weekly contracts will not have a full 30-session history.",
    }


def _intraday_exit_events(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if "snapshot_time" not in frame.columns or frame["snapshot_time"].notna().sum() == 0:
        return []
    events = []
    grouped = frame.dropna(subset=["snapshot_time"]).sort_values("snapshot_time").groupby(
        ["expiry", "strike", "option_type"]
    )
    for (expiry, strike, side), group in grouped:
        group = group.copy()
        group["premium_pct"] = group["ltp"].pct_change() * 100
        group["oi_pct"] = group["oi"].pct_change() * 100
        group["volume_delta"] = group["volume"].diff().clip(lower=0)
        baseline = group["volume_delta"].rolling(10, min_periods=3).median()
        mask = (group["premium_pct"] >= 8) & (group["oi_pct"] <= -3) & (
            (baseline.isna()) | (group["volume_delta"] >= baseline * 2)
        )
        for _, row in group[mask].iterrows():
            events.append({
                "expiry": str(pd.Timestamp(expiry).date()),
                "strike": float(strike),
                "side": side,
                "time": pd.Timestamp(row["snapshot_time"]).isoformat(),
                "observed_premium": float(row["ltp"]),
                "premium_change_pct": round(float(row["premium_pct"]), 2),
                "oi_change_pct": round(float(row["oi_pct"]), 2),
                "classification": "possible_short_covering_pressure",
                "warning": "Observed market-wide pattern, not proof of seller panic or seller entry price.",
            })
    return events


def analyze_option_chain(frame: pd.DataFrame, expiry: str | None = None) -> dict[str, Any]:
    data = _normalise_columns(frame)
    latest_date = data["trade_date"].max()
    latest_all = data[data["trade_date"] == latest_date]
    if expiry:
        selected_expiry = pd.to_datetime(expiry).date()
        expiry_data = data[data["expiry"].dt.date == selected_expiry]
        if expiry_data.empty:
            raise ValueError(f"No rows for expiry {selected_expiry}.")
    else:
        selected_expiry = min(
            latest_all["expiry"].dt.date.unique(),
            key=lambda d: (d - latest_date.date()).days if d >= latest_date.date() else 99999
        )
        expiry_data = data[data["expiry"].dt.date == selected_expiry]
    latest = expiry_data[expiry_data["trade_date"] == latest_date]
    if latest.empty:
        raise ValueError("Selected expiry has no rows on the latest available trading date.")
    spot = float(latest["spot"].median())
    dates = sorted(expiry_data["trade_date"].unique())
    prev = expiry_data[expiry_data["trade_date"] == dates[-2]] if len(dates) > 1 else expiry_data.iloc[0:0]
    strike_diffs = sorted(latest["strike"].drop_duplicates().diff().dropna().tolist())
    step = float(pd.Series(strike_diffs).median()) if strike_diffs else 50.0
    ce_rows = _side_snapshot(latest, prev, "CE", spot)
    pe_rows = _side_snapshot(latest, prev, "PE", spot)
    latest_ce = latest[latest["option_type"] == "CE"]
    latest_pe = latest[latest["option_type"] == "PE"]
    clusters = (
        _cluster_rows(latest, "CE", spot, step)
        + _cluster_rows(latest, "PE", spot, step)
    )
    intraday_events = _intraday_exit_events(expiry_data)
    return {
        "symbol": "NIFTY",
        "as_of": str(latest_date.date()),
        "selected_expiry": str(selected_expiry),
        "spot": round(spot, 2),
        "sessions_available_for_expiry": len(dates),
        "windows": {
            "one_week": _window_metrics(expiry_data, 5),
            "one_month": _window_metrics(expiry_data, 22),
        },
        "seller_cluster_candidates": clusters,
        "ce_candidates": ce_rows,
        "pe_candidates": pe_rows,
        "possible_exit_pressure_events": intraday_events,
        "premium_panic_threshold": {
            "status": "requires_intraday_history" if not intraday_events else "historical_events_detected",
            "value": None,
            "explanation": "EOD data cannot identify an exact panic-exit premium. Use timestamped intraday option-chain snapshots to estimate repeatable premium zones where rising premium coincides with falling OI and expanding volume.",
        },
        "limitations": [
            "OI is open contracts with both a long and short side; public option-chain data does not identify which participant wrote them.",
            "Candidate scores are ranking heuristics, not probabilities or trading signals.",
            "One-month history for a weekly expiry is limited to the sessions that contract actually existed.",
            "Exact seller entry price and panic-exit premium cannot be recovered from EOD OI alone.",
        ],
    }
