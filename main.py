from flask import Flask, jsonify, request
from datetime import datetime
from typing import List, Dict, Any
import json
import os

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
    "core10": [],
    "snapshot_data": {}
}


# --------------------------------------------------
# PIPELINE SIMULATION (with real snapshot_service)
# --------------------------------------------------

def simulate_pipeline_run() -> None:
    """Simulate morning pipeline and fill pipeline_state + result_state."""
    global pipeline_state, result_state

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
    # 1) snapshot_service (GERÇEK)
    # ---------------------------------------------
    snap_start = now_iso()
    symbols = load_symbols()
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

    # log yaz
    log_write("snapshot_service", {
        "status": "OK",
        "start_time": snap_start,
        "end_time": snap_end,
        "retry_count": 0,
        "error": None,
        "output_summary": snapshot_result
    })

    # ---------------------------------------------
    # 2–10) diğer modüller (dummy)
    # ---------------------------------------------
    for name in module_names[1:]:
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

        # her modül için dummy log
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
    #  ŞEMA SABİTLEME: radar/core10 dummy ama TAM alanlı
    # --------------------------------------------------
    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    # Radar listesi: ilk N sembolden dummy skorlar
    radar_list: List[Dict[str, Any]] = []
    for i, sym in enumerate(symbols[:20]):
        base_score = 60.0 + i  # dummy
        adj_score = base_score + 2.0
        radar_list.append({
            "date": today_str,
            "symbol": sym,
            "base_score": base_score,
            "macro_mult": 1.0,
            "atr_pct": 0.03,      # %3 dummy
            "sector": "",
            "volume": 1_000_000 + i * 10_000,
            "adj_score": adj_score,
        })

    # Core10 listesi: radar_list'in ilk 10 elemanından dummy seçim
    core10_list: List[Dict[str, Any]] = []
    for rank, r in enumerate(radar_list[:10], start=1):
        core10_list.append({
            "date": r["date"],
            "symbol": r["symbol"],
            "base_score": r["base_score"],
            "macro_trend": "GREEN",
            "macro_mult": r["macro_mult"],
            "atr_pct": r["atr_pct"],
            "volume": r["volume"],
            "rank_today": rank,
            "adj_score": r["adj_score"],
            "rr_expected": 2.0,           # dummy RR
            "oneD_pass": True,
            "fourH_pass": True,
            "fourH_score": 60.0,
            "fourH_state": "4H_OK",
            "symbol_risk_color": "GREEN",
            "status": "WATCHING",
            "days_held": 1,
            "reason": "ENTER: dummy",
            "entry_price": 100.0 + rank,  # dummy
            "last_price": 100.0 + rank,
            "last_update": today_str + " 10:00:00",
        })

    # BUILD RESULT PAYLOAD
    result_state = {
        "result_ready": True,
        "last_run": end_time,
        "snapshot_data": snapshot_result,  # <-- gerçek snapshot burada
        "radar": radar_list,
        "core10": core10_list
    }


# --------------------------------------------------
# ENDPOINTS
# --------------------------------------------------

@app.route("/", methods=["GET"])
def root():
    return "T4 backend running", 200


@app.route("/runMorningPipeline", methods=["POST"])
def run_morning_pipeline():
    simulate_pipeline_run()
    return jsonify({
        "status": "ok",
        "message": "dummy pipeline + real snapshot completed",
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
