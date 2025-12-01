# modules/radar_engine.py

from typing import List, Dict, Any, Optional
from datetime import date, datetime


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

        - candidates_debug:
            radar_picks_debug tablosuna yazılacak detay skor verisi.

        - picks:
            radar_picks tablosuna yazılacak ana radar listesi.
    """
    # Burada şimdilik sadece iskelet bırakıyoruz.
    # Bir sonraki basamakta, GAS'teki buildRadarPlus fonksiyonunun
    # tüm skor ve filtre mantığını birebir buraya port edeceğiz.

    # Geçici boş dönüş (dummy). Uygulamada bu haliyle kullanılmamalı.
    return {
        "latest_date": "",
        "candidates_debug": [],
        "picks": [],
        "summary": {
            "latest": "",
            "candidates": 0,
            "picked": 0,
            "macro_trend": macro_trend,
            "macro_mult": macro_mults.get(macro_trend, macro_mults.get("DEFAULT", 1.0)),
        },
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
