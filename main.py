from flask import Flask, jsonify, request
from datetime import datetime
from typing import List, Dict, Any
import json
import os

app = Flask(__name__)

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

    end_time = now_iso()

    pipeline_state["pipeline_status"] = "COMPLETED"
    pipeline_state["end_time"] = end_time
    pipeline_state["modules"] = modules

    # --------------------------------------------------
    # BUILD RESULT PAYLOAD
    # --------------------------------------------------
    result_state = {
        "result_ready": True,
        "last_run": end_time,
        "snapshot_data": snapshot_result,  # <-- gerçek snapshot burada
        "radar": [
            {"symbol": "AAAA.IS", "score": 0.85},
            {"symbol": "BBBB.IS", "score": 0.80},
        ],
        "core10": [
            {"symbol": "CCCC.IS", "rank": 1},
            {"symbol": "DDDD.IS", "rank": 2},
        ]
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
