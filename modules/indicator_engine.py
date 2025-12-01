# modules/indicator_engine.py

from typing import List, Dict, Any
from datetime import datetime


def run_indicator_engine(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Indicator engine:
    - ŞİMDİLİK: snapshot'tan gelen sembollerden dummy radar_candidates üretir.
    - UZUN VADEDE: fiyat/indikatör datasından gerçek radar_candidates hesabı burada yapılacak.

    context beklenenler:
      - "symbols": List[str]

    dönüş:
      {
        "radar_candidates": [ {...}, ... ]
      }
    """
    symbols: List[str] = context.get("symbols", []) or []

    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    radar_candidates: List[Dict[str, Any]] = []
    # Şimdilik: ilk 10 sembolden candidate üret
    for i, sym in enumerate(symbols[:10]):
        radar_candidates.append({
            "date": today_str,
            "symbol": sym,
            "volume": 2_000_000 + i * 100_000,  # LIQ_MIN üzerinde
            "atr_pct": 0.08,                    # %8 ATR
            "mom_5d": 0.02 + 0.001 * i,         # %2 civarı kısa vade momentum
            "mom_20d": 0.05 + 0.001 * i,        # %5 civarı orta vade momentum
            "vol_z20": 1.5,
            "rsi_14": 55.0,
            "macd": 0.5,
            "adx14": 22.0,
            "cci20": 100.0,
            "vol_trend": 0.5,
            "close": 100.0 + i,
            "ema20": 98.0 + i,
            "ema50": 95.0 + i,
        })

    return {
        "radar_candidates": radar_candidates
    }
