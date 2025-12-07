from flask import Flask, jsonify, request
from datetime import datetime
from typing import List, Dict, Any, Optional
import json
import os

from modules.radar_engine import run_radar_engine
from modules.fetch_engine import run_fetch_engine
from modules.indicator_engine import run_indicator_engine  # <--- EKLENDİ

app = Flask(__name__)

# --------------------------------------------------
# LOG HELPERS
# --------------------------------------------------

LOG_DIR = "logs"


def ensure_log_dir() -> None:
    """Ensure logs directory exists."""
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)


def log_write(module_name: str, entry: dict) -> None:
    """
    T4 backend modül log giriş noktası.
    Her modül çalıştığında o güne ait log dosyasına ek yapar.
    """
    ensure_log_dir()

    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    log_path = os.path.join(LOG_DIR, f"{date_str}_pipeline.json")

    # Var olan logu oku
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"date": date_str, "modules": []}
    else:
        data = {"date": date_str, "modules": []}

    # Yeni kayıt ekle
    data["modules"].append({
        "module": module_name,
        "ts": datetime.utcnow().isoformat() + "Z",
        **entry
    })

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def now_iso() -> str:
    """Return current UTC time as ISO string."""
    return datetime.utcnow().isoformat() + "Z"


def load_symbols() -> List[str]:
    """Load symbols from symbols_list.json"""
    try:
        path = "symbols_list.json"
        if not os.path.exists(path):
            print("symbols_list.json not found.")
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            else:
                return []
    except Exception as e:
        print("load_symbols ERROR:", e)
        return []


def build_candles_by_symbol(fetch_result: Dict[str, Any]) -> Dict[str, Dict[str, List[Any]]]:
    """
    fetch_engine çıktısını indicator_engine'in istediği candles_by_symbol formatına dönüştürür.

    fetch_result["data"][sym] = [
        {"date": "YYYY-MM-DD", "open": ..., "high": ..., "low": ..., "close": ..., "volume": ...},
        ...
    ]

    dönüş:
    {
      sym: {
        "date": [...],
        "t": [...],    # epoch (UTC midnight)
        "o": [...],
        "h": [...],
        "l": [...],
        "c": [...],
        "v": [...],
      },
      ...
    }
    """
    import time
    from datetime import datetime as dt

    out: Dict[str, Dict[str, List[Any]]] = {}
    data = fetch_result.get("data", {}) or {}

    for sym, rows in data.items():
        if not rows:
            continue

        dates: List[str] = []
        t_list: List[float] = []
        o_list: List[float] = []
        h_list: List[float] = []
        l_list: List[float] = []
        c_list: List[float] = []
        v_list: List[float] = []

        for r in rows:
            ds = str(r.get("date"))
            dates.append(ds)

            # date → epoch (UTC midnight)
            try:
                dtt = dt.strptime(ds, "%Y-%m-%d")
                epoch = time.mktime(dtt.timetuple())
            except Exception:
                epoch = None
            t_list.append(epoch)

            o_list.append(float(r.get("open", 0.0)))
            h_list.append(float(r.get("high", 0.0)))
            l_list.append(float(r.get("low", 0.0)))
            c_list.append(float(r.get("close", 0.0)))
            v_list.append(float(r.get("volume", 0.0)))

        out[sym] = {
            "date": dates,
            "t": t_list,
            "o": o_list,
            "h": h_list,
            "l": l_list,
            "c": c_list,
            "v": v_list,
        }

    return out


# --------------------------------------------------
# GLOBAL STATE
# --------------------------------------------------

pipeline_state: Dict[str, Any] = {
    "pipeline_status": "IDLE",
    "start_time": None,
    "end_time": None,
    "modules": []
}

result_state: Dict[str, Any] = {
    "result_ready": False,
    "last_run": None,
    "radar": [],
    "radar_debug": [],
    "radar_summary": {},
    "radar_api": [],
    "core10": [],
    "snapshot_data": {}
}


# --------------------------------------------------
# PIPELINE SIMULATION (with real fetch + indicator + radar)
# --------------------------------------------------

def simulate_pipeline_run(context: Optional[Dict[str, Any]] = None) -> None:
    """Simulate morning pipeline and fill pipeline_state + result_state."""
    global pipeline_state, result_state

    ctx: Dict[str, Any] = context or {}

    # symbols: öncelik → context.symbols, yoksa load_symbols()
    symbols = ctx.get("symbols")
    if not symbols:
        symbols = load_symbols()
    if not isinstance(symbols, list):
        symbols = list(symbols)

    # lookback_days: context.lookback_days varsa kullan, yoksa 120
    lookback_raw = ctx.get("lookback_days")
    try:
        lookback_days = int(lookback_raw) if lookback_raw is not None else 120
    except Exception:
        lookback_days = 120

    start_time = now_iso()

    module_names: List[str] = [
        "snapshot_service",
        "fetch_engine",
        "repair_engine",
        "indicator_engine",
        "radar_engine",
        "regime_engine",
        "core10_engine",
        "tuning_engine",
        "results_aggregator",
        "state_manager",
    ]

    modules: List[Dict[str, Any]] = []

    # Mark pipeline running
    pipeline_state = {
        "pipeline_status": "RUNNING",
        "start_time": start_time,
        "end_time": None,
        "modules": []
    }

    # ---------------------------------------------
    # 1) SNAPSHOT SERVICE (GERÇEK)
    # ---------------------------------------------
    snap_start = now_iso()
    snapshot_result = {
        "count": len(symbols),
        "symbols": symbols
    }
    snap_end = now_iso()

    modules.append({
        "name": "snapshot_service",
        "status": "OK",
        "start_time": snap_start,
        "end_time": snap_end,
        "retry_count": 0,
        "error": None,
        "result": snapshot_result
    })

    log_write("snapshot_service", {
        "status": "OK",
        "start_time": snap_start,
        "end_time": snap_end,
        "retry_count": 0,
        "error": None,
        "output_summary": snapshot_result
    })

    # ---------------------------------------------
    # 2) FETCH ENGINE (GERÇEK FİYAT VERİSİ)
    # ---------------------------------------------
    fetch_start = now_iso()
    fetch_context: Dict[str, Any] = {
        "symbols": symbols,
        "lookback_days": lookback_days
    }
    fetch_result = run_fetch_engine(fetch_context)
    fetch_end = now_iso()

    fetched_symbols = list((fetch_result.get("data") or {}).keys())
    fetch_errors = fetch_result.get("errors", []) or []

    modules.append({
        "name": "fetch_engine",
        "status": fetch_result.get("status", "ERROR"),
        "start_time": fetch_start,
        "end_time": fetch_end,
        "retry_count": 0,
        "error": None if fetch_result.get("status") == "OK" else "fetch_engine error",
        "result": {
            "as_of": fetch_result.get("as_of"),
            "lookback_days": fetch_result.get("lookback_days"),
            "symbols_requested": len(symbols),
            "symbols_with_data": len(fetched_symbols),
            "error_count": len(fetch_errors),
        }
    })

    log_write("fetch_engine", {
        "status": fetch_result.get("status", "ERROR"),
        "start_time": fetch_start,
        "end_time": fetch_end,
        "retry_count": 0,
        "error": None if fetch_result.get("status") == "OK" else "fetch_engine error",
        "output_summary": {
            "as_of": fetch_result.get("as_of"),
            "lookback_days": fetch_result.get("lookback_days"),
            "symbols_requested": len(symbols),
            "symbols_with_data": len(fetched_symbols),
            "error_count": len(fetch_errors),
            "sample_symbol": fetched_symbols[0] if fetched_symbols else None,
        }
    })

    # --------------------------------------------------
    # 3) INDICATOR ENGINE (GERÇEK) → radar_candidates üret
    # --------------------------------------------------
    ind_start = now_iso()

    candles_by_symbol = build_candles_by_symbol(fetch_result)

    ind_context: Dict[str, Any] = {
        "symbols": fetched_symbols,
        "candles_by_symbol": candles_by_symbol,
        "config": {}  # İleride ATR risk eşikleri vs. buradan geçer
    }

    ind_result = run_indicator_engine(ind_context)
    radar_candidates_struct = ind_result.get("radar_candidates", []) or []

    ind_end = now_iso()

    modules.append({
        "name": "indicator_engine",
        "status": "OK",
        "start_time": ind_start,
        "end_time": ind_end,
        "retry_count": 0,
        "error": None,
        "result": {
            "radar_candidates": len(radar_candidates_struct),
            "dummy": False,
        }
    })

    log_write("indicator_engine", {
        "status": "OK",
        "start_time": ind_start,
        "end_time": ind_end,
        "retry_count": 0,
        "error": None,
        "output_summary": {
            "radar_candidates": len(radar_candidates_struct),
            "dummy": False,
        }
    })

    # --------------------------------------------------
    # 4) DUMMY REGIME ENGINE → basit regime_info üret
    # --------------------------------------------------
    reg_start = now_iso()

    regime_info: Dict[str, Any] = {
        "regime": "YELLOW"  # şimdilik sabit, ileride gerçek rejim motoru gelecek
    }

    reg_end = now_iso()

    modules.append({
        "name": "regime_engine",
        "status": "OK",
        "start_time": reg_start,
        "end_time": reg_end,
        "retry_count": 0,
        "error": None,
        "result": regime_info
    })

    log_write("regime_engine", {
        "status": "OK",
        "start_time": reg_start,
        "end_time": reg_end,
        "retry_count": 0,
        "error": None,
        "output_summary": regime_info
    })

    # --------------------------------------------------
    # 5) RADAR ENGINE (GERÇEK MOTOR)
    # indicator_engine çıktısını flat formata çevirip besliyoruz.
    # --------------------------------------------------
    radar_start = now_iso()

    radar_candidates_flat: List[Dict[str, Any]] = []

    for rc in radar_candidates_struct:
        sym = rc.get("symbol")
        dt_str = rc.get("date")
        ind = rc.get("indicators", {}) or {}

        radar_candidates_flat.append({
            "date": dt_str,
            "symbol": sym,
            "volume": ind.get("volume"),
            "atr_pct": ind.get("atr_pct"),
            "mom_5d": ind.get("mom5"),
            "mom_20d": ind.get("mom20"),
            "vol_z20": ind.get("vol_z20"),
            "rsi_14": ind.get("rsi14"),
            "ema20": ind.get("ema20"),
            "ema50": ind.get("ema50"),
            "adx14": ind.get("adx14"),
            "macd": ind.get("macd"),
            "cci20": ind.get("cci20"),
            "vol_trend": ind.get("vol_trend"),
            "close": ind.get("close"),
            # "sector": ...   # istersek ileride ekleriz
        })

    radar_context: Dict[str, Any] = {
        "radar_candidates": radar_candidates_flat,
        "regime": regime_info,
        "config": {
            "macro_mult_GREEN": 1.05,
            "macro_mult_YELLOW": 1.00,
            "macro_mult_RED": 0.90,
            # İleride RADAR_LIQ_MIN vb. eklenebilir
        },
    }

    radar_output = run_radar_engine(radar_context)
    radar_end = now_iso()

    radar_picks: List[Dict[str, Any]] = radar_output.get("radar", []) or []
    radar_debug: List[Dict[str, Any]] = radar_output.get("radar_debug", []) or []
    radar_summary: Dict[str, Any] = radar_output.get("radar_summary", {}) or {}
    radar_api: List[Dict[str, Any]] = radar_output.get("radar_api", []) or []

    modules.append({
        "name": "radar_engine",
        "status": "OK",
        "start_time": radar_start,
        "end_time": radar_end,
        "retry_count": 0,
        "error": None,
        "result": {
            "picked": len(radar_picks),
            "candidates": len(radar_debug),
            "summary": radar_summary,
        }
    })

    log_write("radar_engine", {
        "status": "OK",
        "start_time": radar_start,
        "end_time": radar_end,
        "retry_count": 0,
        "error": None,
        "output_summary": {
            "picked": len(radar_picks),
            "candidates": len(radar_debug),
            "latest": radar_summary.get("latest"),
            "radar_api_rows": len(radar_api),
        }
    })

    # ---------------------------------------------
    # 6) diğer modüller (dummy log)
    # ---------------------------------------------
    for name in module_names:
        if name in (
            "snapshot_service",
            "fetch_engine",
            "indicator_engine",
            "radar_engine",
            "regime_engine",
        ):
            continue

        m_start = now_iso()
        m_end = now_iso()

        modules.append({
            "name": name,
            "status": "OK",
            "start_time": m_start,
            "end_time": m_end,
            "retry_count": 0,
            "error": None
        })

        log_write(name, {
            "status": "OK",
            "start_time": m_start,
            "end_time": m_end,
            "retry_count": 0,
            "error": None,
            "output_summary": {}
        })

    end_time = now_iso()
    pipeline_state["pipeline_status"] = "COMPLETED"
    pipeline_state["end_time"] = end_time
    pipeline_state["modules"] = modules

    # --------------------------------------------------
    # 7) CORE10 DUMMY (radar üzerinden)
    # --------------------------------------------------
    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    core10_list: List[Dict[str, Any]] = []
    for rank, r in enumerate(radar_picks[:10], start=1):
        core10_list.append({
            "date": r.get("date", today_str),
            "symbol": r.get("symbol"),
            "base_score": r.get("base_score"),
            "macro_trend": regime_info.get("regime", "YELLOW"),
            "macro_mult": r.get("macro_mult"),
            "atr_pct": r.get("atr_pct"),
            "volume": r.get("volume"),
            "rank_today": rank,
            "adj_score": r.get("adj_score"),
            "rr_expected": 2.0,  # dummy RR
            "oneD_pass": True,
            "fourH_pass": True,
            "fourH_score": 60.0,
            "fourH_state": "4H_OK",
            "symbol_risk_color": "GREEN",
            "status": "WATCHING",
            "days_held": 1,
            "reason": "ENTER: dummy",
            "entry_price": r.get("close") or 0.0,
            "last_price": r.get("close") or 0.0,
            "last_update": today_str + " 10:00:00",
        })

    # --------------------------------------------------
    # 8) RESULT PAYLOAD
    # --------------------------------------------------
    result_state = {
        "result_ready": True,
        "last_run": end_time,
        "snapshot_data": snapshot_result,
        "radar": radar_picks,
        "radar_debug": radar_debug,
        "radar_summary": radar_summary,
        "radar_api": radar_api,
        "core10": core10_list,
    }


# --------------------------------------------------
# ENDPOINTS
# --------------------------------------------------

@app.route("/", methods=["GET"])
def root():
    return "T4 backend running", 200


@app.route("/runMorningPipeline", methods=["POST"])
def run_morning_pipeline():
    # GAS'ten gelen JSON body'yi al
    data = request.get_json(silent=True) or {}

    symbols = data.get("symbols")
    lookback_days = data.get("lookback_days")

    ctx: Dict[str, Any] = {
        "symbols": symbols,
        "lookback_days": lookback_days,
    }

    try:
        simulate_pipeline_run(ctx)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print("PIPELINE_ERROR:", tb)
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": tb
        }), 500

    return jsonify({
        "status": "ok",
        "message": "pipeline completed",
        "pipeline_status": pipeline_state["pipeline_status"],
        "start_time": pipeline_state["start_time"],
        "end_time": pipeline_state["end_time"],
    }), 200


@app.route("/status", methods=["GET"])
def status():
    return jsonify(pipeline_state), 200


@app.route("/result", methods=["GET"])
def result():
    return jsonify(result_state), 200


@app.route("/logs/today", methods=["GET"])
def logs_today():
    """
    Bugüne ait pipeline log dosyasını JSON olarak döner.
    Dosya yoksa basit bir mesaj döner.
    """
    ensure_log_dir()

    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    log_path = os.path.join(LOG_DIR, f"{date_str}_pipeline.json")

    if not os.path.exists(log_path):
        return jsonify({
            "date": date_str,
            "message": "No log file for today."
        }), 200

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data), 200
    except Exception as e:
        return jsonify({
            "date": date_str,
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
