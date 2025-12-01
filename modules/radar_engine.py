# modules/radar_engine.py

from typing import List, Dict, Any, Optional
from datetime import date, datetime
from math import isfinite


def _normalize_date_to_str(d: Any) -> str:
    """
    Internal helper: date/datetime/string değerlerini 'YYYY-MM-DD' stringine çevirir.
    Backend içinde tek tip tarih formatı kullanmak için.
    """
    if isinstance(d, date):
        return d.strftime("%Y-%m-%d")
    if isinstance(d, datetime):
        return d.date().strftime("%Y-%m-%d")
    if isinstance(d, str):
        return d[:10]
    return ""


def compute_radar_from_candidates(
    radar_candidates: List[Dict[str, Any]],
    macro_trend: str,
    macro_mults: Dict[str, float],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    T4 radar motoru – GAS buildRadarPlus fonksiyonunun Python portu.
    Girdi: radar_candidates → dict listesi (her eleman bir satır).
    """
    config = config or {}

    # --- Config / sabitler ---
    # LIQ_MIN: ister config'ten, ister default 1.000.000
    liq_min = float(config.get("RADAR_LIQ_MIN", 1_000_000))

    # Sektör limiti şimdilik kapalı (GAS: USE_SECTOR_CAP = false)
    use_sector_cap = bool(config.get("RADAR_USE_SECTOR_CAP", False))
    sector_cap = int(config.get("RADAR_SECTOR_CAP", 2))

    # Makro çarpan
    macro_trend_u = (macro_trend or "YELLOW").upper()
    macro_mult = macro_mults.get(
        macro_trend_u,
        macro_mults.get("DEFAULT", 1.0),
    )

    # --- latestStr hesapla (en büyük tarih) ---
    latest_str: Optional[str] = None
    for row in radar_candidates:
        d_str = _normalize_date_to_str(row.get("date"))
        if not d_str:
            continue
        if latest_str is None or d_str > latest_str:
            latest_str = d_str

    # Eğer tarih yoksa: boş dönüş
    if not latest_str:
        return {
            "latest_date": "",
            "candidates_debug": [],
            "picks": [],
            "summary": {
                "latest": "",
                "candidates": 0,
                "picked": 0,
                "macro_trend": macro_trend_u,
                "macro_mult": macro_mult,
            },
        }

    def clamp(x: float) -> float:
        return max(0.0, min(100.0, x))

    candidates: List[Dict[str, Any]] = []

    for row in radar_candidates:
        sym = row.get("symbol")
        if not sym:
            continue

        row_str = _normalize_date_to_str(row.get("date"))
        if row_str != latest_str:
            continue

        # --- ATR ---
        atr_val = row.get("atr_pct")
        atr_pct: Optional[float]

        if isinstance(atr_val, str) and "%" in atr_val:
            try:
                atr_pct = float(atr_val.replace("%", "").replace(",", ".")) / 100.0
            except Exception:
                atr_pct = None
        else:
            try:
                atr_pct = float(atr_val) if atr_val is not None else None
            except Exception:
                atr_pct = None

        if atr_pct is not None and not isfinite(atr_pct):
            atr_pct = None

        # --- Volume ---
        try:
            volume = float(row.get("volume") or 0.0)
        except Exception:
            volume = 0.0

        if volume < liq_min:
            continue

        # --- Diğer alanlar (mom, z20, rsi, adx vs.) ---
        def to_float(val) -> Optional[float]:
            try:
                x = float(val)
                return x if isfinite(x) else None
            except Exception:
                return None

        mom5 = to_float(row.get("mom_5d"))
        mom20 = to_float(row.get("mom_20d"))
        z20 = to_float(row.get("vol_z20"))
        rsi = to_float(row.get("rsi_14"))
        macd = to_float(row.get("macd"))     # şimdilik kullanılmıyor
        adx = to_float(row.get("adx14"))
        cci = to_float(row.get("cci20"))     # şimdilik kullanılmıyor
        voltr = to_float(row.get("vol_trend"))
        close = to_float(row.get("close"))
        ema20 = to_float(row.get("ema20"))
        ema50 = to_float(row.get("ema50"))

        # --- Momentum (s_mom) ---
        total_mom = 0.0
        if mom5 is not None:
            total_mom += mom5
        if mom20 is not None:
            total_mom += mom20

        if mom5 is None and mom20 is None:
            s_mom = 50.0
        else:
            s_mom = clamp(50.0 + 500.0 * total_mom)

        # --- Hacim / Anomali (s_vol) ---
        if z20 is None:
            s_vol = 50.0
        else:
            if z20 >= 0:
                s_vol = clamp(50.0 + 35.0 * z20)
            else:
                s_vol = clamp(50.0 + 15.0 * z20)
        if voltr is not None:
            # vol_trend pozitifse hafif bonus, negatifse hafif ceza
            s_vol = clamp(s_vol + voltr * 20.0)

        # --- Trend uyumu (s_trend) ---
        s_trend = 50.0
        if ema20 is not None and ema50 is not None:
            if ema20 > ema50:
                s_trend = 70.0  # uptrend
            elif ema20 < ema50:
                s_trend = 40.0  # downtrend
            else:
                s_trend = 50.0
        if adx is not None:
            if adx >= 25.0:
                s_trend += 10.0
            elif adx >= 15.0:
                s_trend += 5.0
        s_trend = clamp(s_trend)

        # --- Breakout / Konum (s_breakout) ---
        s_breakout = 50.0
        if close is not None and ema20 is not None:
            if close > ema20:
                s_breakout = 75.0
            else:
                s_breakout = 40.0

        # --- Relative Strength (s_rs) - şimdilik nötr ---
        s_rs = 50.0

        # --- ATR cezası (atr_penalty) ---
        atr_penalty = 0.0
        if atr_pct is not None and atr_pct > 0:
            atr_norm = min(atr_pct / 0.15, 1.0)  # %15 ve üstü çok zıplak
            atr_penalty = atr_norm * 10.0        # 0–10 arası ceza

        # --- Base score ---
        base_score = (
            0.30 * s_mom +
            0.20 * s_vol +
            0.25 * s_trend +
            0.15 * s_breakout +
            0.10 * s_rs
        )
        base_clamped = clamp(base_score)

        # --- Makro + ATR cezası ---
        core_raw = base_clamped * macro_mult
        adj_score = core_raw - atr_penalty

        candidates.append({
            "date": latest_str,           # GAS: rowDate/ latestStr → string format
            "symbol": sym,
            "base": base_clamped,
            "macroMult": macro_mult,
            "atr": atr_pct,
            "sector": row.get("sector", "") or "",
            "volume": volume,
            "adj": adj_score,
            "_s_mom": s_mom,
            "_s_vol": s_vol,
            "_s_trend": s_trend,
            "_s_breakout": s_breakout,
            "_s_rs": s_rs,
            "_atrPenalty": atr_penalty,
        })

    # Skora göre sırala (desc)
    candidates.sort(key=lambda x: x["adj"], reverse=True)

    # Picks: şimdilik tüm adaylar (USE_SECTOR_CAP = false ile aynı)
    picks: List[Dict[str, Any]] = []
    if use_sector_cap:
        seen: Dict[str, int] = {}
        for x in candidates:
            key = x["sector"] or "unknown"
            c = seen.get(key, 0)
            if c >= sector_cap:
                continue
            seen[key] = c + 1
            picks.append(x)
    else:
        picks.extend(candidates)

    # Çıktı formatı: radar_picks + radar_picks_debug + summary
    radar_picks = [
        {
            "date": c["date"],
            "symbol": c["symbol"],
            "base_score": c["base"],
            "macro_mult": c["macroMult"],
            "atr_pct": c["atr"],
            "sector": c["sector"],
            "volume": c["volume"],
            "adj_score": c["adj"],
        }
        for c in picks
    ]

    radar_debug = [
        {
            "date": c["date"],
            "symbol": c["symbol"],
            "s_mom": c["_s_mom"],
            "s_vol": c["_s_vol"],
            "s_trend": c["_s_trend"],
            "s_breakout": c["_s_breakout"],
            "s_rs": c["_s_rs"],
            "atr_penalty": c["_atrPenalty"],
            "base_score": c["base"],
            "macro_mult": c["macroMult"],
            "adj_score": c["adj"],
        }
        for c in candidates
    ]

    summary = {
        "latest": latest_str,
        "candidates": len(candidates),
        "picked": len(picks),
        "macro_trend": macro_trend_u,
        "macro_mult": macro_mult,
    }

    return {
        "latest_date": latest_str,
        "candidates_debug": radar_debug,
        "picks": radar_picks,
        "summary": summary,
    }


def run_radar_engine(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pipeline seviyesinde kullanılacak wrapper fonksiyon.

    context:
        snapshot, indicator, regime, config gibi birleşik veriyi içeren dict.
        Bu fonksiyon:
          - context içinden radar_candidates listesini,
          - regime bilgisini,
          - config içinden macro_mult_* değerlerini
        alır ve compute_radar_from_candidates'e geçirir.

    Dönüş:
        {
          "radar": [...],
          "radar_debug": [...],
          "radar_summary": {...}
        }

        Bu yapı doğrudan /result JSON'una gömülebilir.
    """
    radar_candidates = context.get("radar_candidates", [])  # indicator_engine çıktısı
    regime_info = context.get("regime", {})
    macro_trend = str(regime_info.get("regime", "YELLOW")).upper()

    cfg = context.get("config", {}) or {}
    macro_mults = {
        "GREEN": float(cfg.get("macro_mult_GREEN", 1.0)),
        "YELLOW": float(cfg.get("macro_mult_YELLOW", 1.0)),
        "RED": float(cfg.get("macro_mult_RED", 1.0)),
        "DEFAULT": 1.0,
    }

    radar_result = compute_radar_from_candidates(
        radar_candidates=radar_candidates,
        macro_trend=macro_trend,
        macro_mults=macro_mults,
        config=cfg,
    )

    return {
        "radar": radar_result.get("picks", []),
        "radar_debug": radar_result.get("candidates_debug", []),
        "radar_summary": radar_result.get("summary", {}),
    }

