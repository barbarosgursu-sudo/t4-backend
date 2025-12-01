# modules/radar_engine.py

from typing import List, Dict, Any, Optional
from datetime import date, datetime
from math import isfinite


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _to_float(v) -> Optional[float]:
    try:
        x = float(v)
        return x if isfinite(x) else None
    except Exception:
        return None


def _normalize_date_to_str(d: Any) -> str:
    if isinstance(d, date):
        return d.strftime("%Y-%m-%d")
    if isinstance(d, datetime):
        return d.date().strftime("%Y-%m-%d")
    if isinstance(d, str):
        return d[:10]
    return ""


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


# ----------------------------------------------------------------------
# Scoring Functions (clean, atomic)
# ----------------------------------------------------------------------

def score_mom(mom5: Optional[float], mom20: Optional[float]) -> float:
    """
    Momentum skoru: mom5 + mom20 birleşik.
    """
    if mom5 is None and mom20 is None:
        return 50.0

    total = (mom5 or 0.0) + (mom20 or 0.0)
    return _clamp(50.0 + total * 500.0)


def score_vol(z20: Optional[float], voltr: Optional[float]) -> float:
    """
    Hacim / anomaly skoru.
    """
    if z20 is None:
        base = 50.0
    else:
        base = 50.0 + (35.0 * z20 if z20 >= 0 else 15.0 * z20)

    if voltr is not None:
        base += voltr * 20.0

    return _clamp(base)


def score_trend(ema20: Optional[float], ema50: Optional[float], adx: Optional[float]) -> float:
    """
    Trend uyumu + ADX.
    """
    s = 50.0

    if ema20 is not None and ema50 is not None:
        if ema20 > ema50:
            s = 70.0
        elif ema20 < ema50:
            s = 40.0
        else:
            s = 50.0

    if adx is not None:
        if adx >= 25:
            s += 10.0
        elif adx >= 15:
            s += 5.0

    return _clamp(s)


def score_breakout(close: Optional[float], ema20: Optional[float]) -> float:
    if close is None or ema20 is None:
        return 50.0

    return 75.0 if close > ema20 else 40.0


def score_rs() -> float:
    """
    Şimdilik nötr.
    """
    return 50.0


def apply_atr_penalty(atr_pct: Optional[float]) -> float:
    """
    ATR cezası: %15 ve üstü maksimum ceza.
    """
    if atr_pct is None or atr_pct <= 0:
        return 0.0

    atr_norm = min(atr_pct / 0.15, 1.0)
    return atr_norm * 10.0


# ----------------------------------------------------------------------
# Base & Adj Score
# ----------------------------------------------------------------------

def compute_base_score(s_mom, s_vol, s_trend, s_breakout, s_rs) -> float:
    score = (
        0.30 * s_mom +
        0.20 * s_vol +
        0.25 * s_trend +
        0.15 * s_breakout +
        0.10 * s_rs
    )
    return _clamp(score)


def compute_adj_score(base, macro_mult, atr_penalty) -> float:
    return (base * macro_mult) - atr_penalty


# ----------------------------------------------------------------------
# Picks / Sector Cap
# ----------------------------------------------------------------------

def pick_filter(
    candidates: List[Dict[str, Any]],
    use_sector_cap: bool,
    sector_cap: int
) -> List[Dict[str, Any]]:
    if not use_sector_cap:
        return candidates.copy()

    seen = {}
    picks = []

    for row in candidates:
        sector = (row.get("sector") or "UNKNOWN").upper()
        used = seen.get(sector, 0)

        if used < sector_cap:
            picks.append(row)
            seen[sector] = used + 1

    return picks


# ----------------------------------------------------------------------
# Main Radar Engine
# ----------------------------------------------------------------------

def compute_radar(candidates_raw: List[Dict[str, Any]],
                  macro_trend: str,
                  macro_mults: Dict[str, float],
                  cfg: Dict[str, Any]) -> Dict[str, Any]:

    macro_u = macro_trend.upper()
    macro_mult = macro_mults.get(macro_u, macro_mults.get("DEFAULT", 1.0))

    # Likidite eşiği
    liq_min = float(cfg.get("RADAR_LIQ_MIN", 1_000_000))
    use_sector_cap = bool(cfg.get("RADAR_USE_SECTOR_CAP", False))
    sector_cap = int(cfg.get("RADAR_SECTOR_CAP", 2))

    # En yeni tarih
    latest = ""
    for r in candidates_raw:
        d = _normalize_date_to_str(r.get("date"))
        if d and d > latest:
            latest = d

    if not latest:
        return {
            "latest_date": "",
            "candidates_debug": [],
            "picks": [],
            "summary": {
                "latest": "",
                "candidates": 0,
                "picked": 0,
                "macro_trend": macro_u,
                "macro_mult": macro_mult,
            }
        }

    # ------------------------------------------------------------
    # Score candidates
    # ------------------------------------------------------------
    scored = []

    for r in candidates_raw:
        if _normalize_date_to_str(r.get("date")) != latest:
            continue

        volume = _to_float(r.get("volume")) or 0.0
        if volume < liq_min:
            continue

        mom5 = _to_float(r.get("mom_5d"))
        mom20 = _to_float(r.get("mom_20d"))
        z20 = _to_float(r.get("vol_z20"))
        rsi = _to_float(r.get("rsi_14"))
        macd = _to_float(r.get("macd"))
        adx = _to_float(r.get("adx14"))
        cci = _to_float(r.get("cci20"))
        voltr = _to_float(r.get("vol_trend"))
        close = _to_float(r.get("close"))
        ema20 = _to_float(r.get("ema20"))
        ema50 = _to_float(r.get("ema50"))

        # ATR parse
        atr_raw = r.get("atr_pct")
        if isinstance(atr_raw, str) and "%" in atr_raw:
            try:
                atr_pct = float(atr_raw.replace("%", "").replace(",", ".")) / 100.0
            except Exception:
                atr_pct = None
        else:
            atr_pct = _to_float(atr_raw)

        # score components
        s_mom = score_mom(mom5, mom20)
        s_vol = score_vol(z20, voltr)
        s_trend = score_trend(ema20, ema50, adx)
        s_breakout = score_breakout(close, ema20)
        s_rs = score_rs()

        base = compute_base_score(s_mom, s_vol, s_trend, s_breakout, s_rs)
        atr_pen = apply_atr_penalty(atr_pct)
        adj = compute_adj_score(base, macro_mult, atr_pen)

        scored.append({
            "date": latest,
            "symbol": r.get("symbol"),
            "base_score": base,
            "macro_mult": macro_mult,
            "atr_pct": atr_pct,
            "sector": r.get("sector") or "",
            "volume": volume,
            "adj_score": adj,
            "_s_mom": s_mom,
            "_s_vol": s_vol,
            "_s_trend": s_trend,
            "_s_breakout": s_breakout,
            "_s_rs": s_rs,
            "_atr_penalty": atr_pen,
        })

    # Sıralama
    scored.sort(key=lambda x: x["adj_score"], reverse=True)

    # Picks
    picks = pick_filter(scored, use_sector_cap, sector_cap)

    # Debug
    debug = [
        {
            "date": r["date"],
            "symbol": r["symbol"],
            "s_mom": r["_s_mom"],
            "s_vol": r["_s_vol"],
            "s_trend": r["_s_trend"],
            "s_breakout": r["_s_breakout"],
            "s_rs": r["_s_rs"],
            "atr_penalty": r["_atr_penalty"],
            "base_score": r["base_score"],
            "macro_mult": r["macro_mult"],
            "adj_score": r["adj_score"],
        }
        for r in scored
    ]

    summary = {
        "latest": latest,
        "candidates": len(scored),
        "picked": len(picks),
        "macro_trend": macro_u,
        "macro_mult": macro_mult,
    }

    return {
        "latest_date": latest,
        "candidates_debug": debug,
        "picks": picks,
        "summary": summary,
    }


# ----------------------------------------------------------------------
# Public Wrapper (pipeline-level)
# ----------------------------------------------------------------------

def run_radar_engine(context: Dict[str, Any]) -> Dict[str, Any]:
    raw = context.get("radar_candidates", [])
    regime = context.get("regime", {})
    cfg = context.get("config", {}) or {}

    macro_trend = str(regime.get("regime", "YELLOW")).upper()

    macro_mults = {
        "GREEN": float(cfg.get("macro_mult_GREEN", 1.0)),
        "YELLOW": float(cfg.get("macro_mult_YELLOW", 1.0)),
        "RED": float(cfg.get("macro_mult_RED", 1.0)),
        "DEFAULT": 1.0
    }

    result = compute_radar(
        candidates_raw=raw,
        macro_trend=macro_trend,
        macro_mults=macro_mults,
        cfg=cfg,
    )

    return {
        "radar": result["picks"],
        "radar_debug": result["candidates_debug"],
        "radar_summary": result["summary"],
    }
