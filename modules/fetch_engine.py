# modules/fetch_engine.py

from typing import Dict, Any, List
from datetime import datetime, timedelta

import yfinance as yf


def run_fetch_engine(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch engine:
    - Yahoo Finance üzerinden verilen semboller için OHLCV verisi çeker.
    - indicator_engine ve diğer modüller tarafından kullanılacak ham veri yapısını döndürür.

    Beklenen context:
      - "symbols": List[str]
      - "lookback_days": int
      - (opsiyonel) "as_of": "YYYY-MM-DD" (string)

    Dönüş:
      {
        "status": "OK" | "ERROR",
        "as_of": "YYYY-MM-DD",
        "lookback_days": int,
        "symbols": [...],
        "data": { symbol: [ {date, open, high, low, close, volume}, ... ] },
        "errors": List[str]  # sembol bazlı uyarılar
      }
    """
    symbols: List[str] = context.get("symbols", []) or []
    lookback_days: int = int(context.get("lookback_days", 120) or 120)

    # Tarih aralığı
    if "as_of" in context and context["as_of"]:
        try:
            as_of_dt = datetime.strptime(context["as_of"], "%Y-%m-%d")
        except Exception:
            as_of_dt = datetime.utcnow()
    else:
        as_of_dt = datetime.utcnow()

    end_dt = as_of_dt
    start_dt = end_dt - timedelta(days=lookback_days)

    as_of_str = as_of_dt.strftime("%Y-%m-%d")

    result_data: Dict[str, List[Dict[str, Any]]] = {}
    errors: List[str] = []

    if not symbols:
        return {
            "status": "ERROR",
            "as_of": as_of_str,
            "lookback_days": lookback_days,
            "symbols": [],
            "data": {},
            "errors": ["No symbols provided to fetch_engine."]
        }

    for sym in symbols:
        try:
            # Yahoo Finance'tan veri çek
            df = yf.download(
                sym,
                start=start_dt.strftime("%Y-%m-%d"),
                end=(end_dt + timedelta(days=1)).strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=False,
            )

            if df is None or df.empty:
                errors.append(f"{sym}: no data returned from Yahoo.")
                continue

            rows: List[Dict[str, Any]] = []
            for idx, row in df.iterrows():
                # idx: Timestamp (tarih), row: OHLCV
                rows.append({
                    "date": idx.strftime("%Y-%m-%d"),
                    "open": float(row.get("Open", 0.0) or 0.0),
                    "high": float(row.get("High", 0.0) or 0.0),
                    "low": float(row.get("Low", 0.0) or 0.0),
                    "close": float(row.get("Close", 0.0) or 0.0),
                    "volume": float(row.get("Volume", 0.0) or 0.0),
                })

            if not rows:
                errors.append(f"{sym}: empty rows after processing Yahoo data.")
                continue

            result_data[sym] = rows

        except Exception as e:
            errors.append(f"{sym}: ERROR {e}")

    status = "OK" if result_data else "ERROR"

    return {
        "status": status,
        "as_of": as_of_str,
        "lookback_days": lookback_days,
        "symbols": symbols,
        "data": result_data,
        "errors": errors,
    }
