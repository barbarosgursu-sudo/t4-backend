# modules/radar_engine.py

from typing import List, Dict, Any, Optional
from datetime import date, datetime


def _normalize_date_to_str(d: Any) -> str:
    """
    Internal helper: date/datetime/string değerlerini 'YYYY-MM-DD' stringine çevirir.
    Backend içinde tek tip tarih formatı kullanmak için.
    """
    if isinstance(d, date) and not isinstance(d, datetime):
        return d.strftime("%Y-%m-%d")
    if isinstance(d, datetime):
        return d.date().strftime("%Y-%m-%d")
    if isinstance(d, str):
        return d[:10]
    return ""


def _to_float(x: Any) -> Optional[float]:
    """
    NaN, None, boş string vs. değerleri güvenli şekilde float'a çevirir.
    Çeviremiyorsa None döner.
    """
    if x is None:
        return None
    if isinstance(x, (int, float)):
        # Inf durumunda None döndür.
        if x != x:  # NaN kontrol
            return None
        return float(x)
    s = str(x).strip()
    if not s:
        return None
    # Yüzde işareti varsa onu da tolere et (GAS'teki atr% parsing benzeri).
    if s.endswith("%"):
        try:
            val = float(s[:-1].replace(",", "."))
            return val / 100.0
        except Exception:
            return None
    try:
        return float(s.replace(",", "."))
    except Exception:
        return None


def _clamp(x: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    return max(min_val, min(max_val, x))


def compute_radar_from_candidates(
    radar_candidates: List[Dict[str, Any]],
    macro_trend: str,
    macro_mults: Dict[str, float],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    T4 radar motorunun çekirdeği.

    Girdi:
        radar_candidates:
            radar_candidates_api tablosundan / indicator_engine çıktısından gelen satırlar.
            Her elemanda en az şu alanlar beklenir:
                - date
                - symbol
                - volume
                - atr_pct
                - mom_5d
                - mom_20d
                - vol_z20
                - rsi_14
                - macd
                - adx14
                - cci20
                - vol_trend
                - close
                - ema20
                - ema50

        macro_trend:
            'GREEN' | 'YELLOW' | 'RED' gibi rejim bilgisi.

        macro_mults:
            Örnek:
                {
                    "GREEN": 1.0,
                    "YELLOW": 0.9,
                    "RED": 0.8,
                    "DEFAULT": 1.0
                }

        config:
            İleride LIQ_MIN, ATR limitleri vb. eşikleri konfige taşımak için opsiyonel dict.

    Dönüş:
        {
            "latest_date": "YYYY-MM-DD",
            "candidates_debug": [...],
            "picks": [...],
            "summary": {
                "latest": "YYYY-MM-DD",
                "candidates": int,
                "picked": int,
                "macro_trend": str,
                "macro_mult": float,
            }
        }
    """
    # --- LIQ_MIN (GAS: sabit 1_000_000) ---
    # Şu an davranışı birebir korumak için default 1_000_000 kullanıyoruz.
    # İstersen config["RADAR_LIQ_MIN"] vb. ile override edebiliriz.
    if config is None:
        config = {}
    try:
        liq_min = float(config.get("RADAR_LIQ_MIN", 1_000_000))
    except Exception:
        liq_min = 1_000_000.0

    # --- Makro çarpan ---
    macro_trend_up = str(macro_trend or "YELLOW").upper()
    macro_mult = float(
        macro_mults.get(
            macro_trend_up,
            macro_mults.get("DEFAULT", 1.0),
        )
    )

    # --- latest_date hesaplama (GAS: latestStr) ---
    latest_str: Optional[str] = None
    for row in radar_candidates:
        d_str = _normalize_date_to_str(row.get("date"))
        if not d_str:
            continue
        if latest_str is None or d_str > latest_str:
            latest_str = d_str

    # Kaynak boşsa / tarih yoksa boş dönüş
    if not latest_str:
        return {
            "latest_date": "",
            "candidates_debug": [],
            "picks": [],
            "summary": {
                "latest": "",
                "candidates": 0,
                "picked": 0,
                "macro_trend": macro_trend_up,
                "macro_mult": macro_mult,
            },
        }

    candidates_debug: List[Dict[str, Any]] = []
    picks: List[Dict[str, Any]] = []

    # --- Her satırı GAS'teki buildRadarPlus mantığı ile işle ---
    for row in radar_candidates:
        symbol = row.get("symbol") or row.get("ticker") or row.get("code")
        if not symbol:
            continue

        row_date_str = _normalize_date_to_str(row.get("date"))
        if row_date_str != latest_str:
            # Sadece en son güne ait satırlar işlenir
            continue

        # ATR parsing (GAS: atr% string ise % işaretinden temizleyip /100 yapıyordu)
        atr_raw = row.get("atr_pct", row.get("atr"))
        atr_pct = _to_float(atr_raw)
        if atr_pct is not None and atr_pct < 0:
            # Negatif ATR saçmalık, None'a çevir.
            atr_pct = None

        # Volume filtresi
        vol = _to_float(row.get("volume"))
        volume = vol if vol is not None else 0.0
        if volume < liq_min:
            # Likidite filtresi (GAS: volume < LIQ_MIN → continue)
            continue

        mom_5d = _to_float(row.get("mom_5d"))
        mom_20d = _to_float(row.get("mom_20d"))
        vol_z20 = _to_float(row.get("vol_z20"))
        rsi_14 = _to_float(row.get("rsi_14"))
        macd = _to_float(row.get("macd"))      # Şu an kullanılmıyor ama debug için hazır.
        adx14 = _to_float(row.get("adx14"))
        cci20 = _to_float(row.get("cci20"))    # Şu an kullanılmıyor ama debug için hazır.
        vol_trend = _to_float(row.get("vol_trend"))

        close = _to_float(row.get("close"))
        ema20 = _to_float(row.get("ema20"))
        ema50 = _to_float(row.get("ema50"))

        # --- Momentum skoru (s_mom) ---
        total_mom = 0.0
        has_any_mom = False
        if mom_5d is not None:
            total_mom += mom_5d
            has_any_mom = True
        if mom_20d is not None:
            total_mom += mom_20d
            has_any_mom = True

        if has_any_mom:
            s_mom = _clamp(50.0 + 500.0 * total_mom)  # GAS: 50 + 500 * totalMom
        else:
            s_mom = 50.0

        # --- Hacim / anomaly skoru (s_vol) ---
        if vol_z20 is None:
            s_vol = 50.0
        else:
            if vol_z20 >= 0:
                s_vol = _clamp(50.0 + 35.0 * vol_z20)
            else:
                s_vol = _clamp(50.0 + 15.0 * vol_z20)

        if vol_trend is not None:
            s_vol = _clamp(s_vol + vol_trend * 20.0)  # ±10 civarı oynama

        # --- Trend skoru (s_trend) ---
        s_trend = 50.0
        if ema20 is not None and ema50 is not None:
            if ema20 > ema50:
                s_trend = 70.0
            elif ema20 < ema50:
                s_trend = 40.0
            else:
                s_trend = 50.0

        if adx14 is not None:
            if adx14 >= 25.0:
                s_trend += 10.0
            elif adx14 >= 15.0:
                s_trend += 5.0

        s_trend = _clamp(s_trend)

        # --- Breakout / konum skoru (s_breakout) ---
        s_breakout = 50.0
        if close is not None and ema20 is not None:
            if close > ema20:
                s_breakout = 75.0
            else:
                s_breakout = 40.0

        # --- RS skoru (şimdilik sabit) ---
        s_rs = 50.0

        # --- ATR cezası (atr_penalty) ---
        atr_penalty = 0.0
        if atr_pct is not None and atr_pct > 0:
            # GAS: const atrNorm = Math.min(atrPct / 0.15, 1);
            atr_norm = min(atr_pct / 0.15, 1.0)
            atr_penalty = atr_norm * 10.0  # 0–10 arası ceza

        # --- Base score (0–100 arası) ---
        base_score = (
            0.30 * s_mom
            + 0.20 * s_vol
            + 0.25 * s_trend
            + 0.15 * s_breakout
            + 0.10 * s_rs
        )
        base_score = _clamp(base_score)

        # --- Makro + ATR cezası ile adj_score ---
        core_raw = base_score * macro_mult
        adj_score = core_raw - atr_penalty

        # Debug candidate (radar_picks_debug)
        candidates_debug.append({
            "date": latest_str,        # GAS: rowDate or latestStr, ama debug'ta zaten aynı güne bakıyoruz
            "symbol": symbol,
            "s_mom": s_mom,
            "s_vol": s_vol,
            "s_trend": s_trend,
            "s_breakout": s_breakout,
            "s_rs": s_rs,
            "atr_penalty": atr_penalty,
            "base_score": base_score,
            "macro_mult": macro_mult,
            "adj_score": adj_score,
            "volume": volume,
            "atr_pct": atr_pct,
        })

        # picks için de aynı objeyi temel alacağız (later: sort & sector cap)
        picks.append({
            "date": latest_str,
            "symbol": symbol,
            "base_score": base_score,
            "macro_mult": macro_mult,
            "atr_pct": atr_pct,
            "sector": "",  # GAS: şu an boş
            "volume": volume,
            "adj_score": adj_score,
        })

    # --- Sıralama (GAS: candidates.sort((a,b) => b.adj - a.adj)) ---
    candidates_debug.sort(key=lambda x: (x.get("adj_score") or 0.0), reverse=True)
    picks.sort(key=lambda x: (x.get("adj_score") or 0.0), reverse=True)

    # Sektör limit mantığı şimdilik kapalı (GAS: USE_SECTOR_CAP = false)
    # İleride aktif edersek burada implement ederiz.

    summary = {
        "latest": latest_str,
        "candidates": len(candidates_debug),
        "picked": len(picks),
        "macro_trend": macro_trend_up,
        "macro_mult": macro_mult,
    }

    return {
        "latest_date": latest_str,
        "candidates_debug": candidates_debug,
        "picks": picks,
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
