import pandas as pd

from app.seller_intelligence import analyze_option_chain


def test_analyzer_builds_cluster_and_windows():
    rows = []
    dates = pd.bdate_range("2026-10-01", periods=8)
    for day_index, day in enumerate(dates):
        for strike in range(24900, 25301, 50):
            for side in ("CE", "PE"):
                oi = 10000 + (strike - 24900) * 10 + day_index * 100
                if side == "CE" and strike in (25100, 25150, 25200):
                    oi += 30000
                if side == "PE" and strike in (25000, 25050):
                    oi += 25000
                rows.append({
                    "trade_date": day.date().isoformat(),
                    "expiry": "2026-10-29",
                    "strike": strike,
                    "option_type": side,
                    "oi": oi,
                    "change_oi": 500 if day_index else 100,
                    "volume": 2000 + day_index * 100,
                    "ltp": 50 - day_index if side == "CE" else 45 - day_index,
                    "spot": 25100 + day_index * 5,
                })
    result = analyze_option_chain(pd.DataFrame(rows))
    assert result["symbol"] == "NIFTY"
    assert result["windows"]["one_week"]["available_sessions"] == 5
    assert result["windows"]["one_month"]["available_sessions"] == 8
    assert isinstance(result["seller_cluster_candidates"], list)
    assert result["premium_panic_threshold"]["value"] is None
