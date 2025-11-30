from flask import Flask, jsonify, request
from datetime import datetime
from typing import List, Dict, Any

app = Flask(__name__)


# In-memory pipeline state (dummy)
pipeline_state: Dict[str, Any] = {
    "pipeline_status": "IDLE",
    "start_time": None,
    "end_time": None,
    "modules": []  # list of {name, status, start_time, end_time, retry_count, error}
}

result_state: Dict[str, Any] = {
    "result_ready": False,
    "last_run": None,
    "radar": [],
    "core10": []
}


def now_iso() -> str:
    """Return current UTC time as ISO string."""
    return datetime.utcnow().isoformat() + "Z"


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

    # Mark pipeline as running
    pipeline_state = {
        "pipeline_status": "RUNNING",
        "start_time": start_time,
        "end_time": None,
        "modules": []
    }

    # Simulate each module as OK
    for name in module_names:
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

    # Dummy result payload
    result_state = {
        "result_ready": True,
        "last_run": end_time,
        "radar": [
            {"symbol": "AAAA.IS", "score": 0.85},
            {"symbol": "BBBB.IS", "score": 0.80},
        ],
        "core10": [
            {"symbol": "CCCC.IS", "rank": 1},
            {"symbol": "DDDD.IS", "rank": 2},
        ]
    }


@app.route("/", methods=["GET"])
def root():
    return "T4 backend running", 200


@app.route("/runMorningPipeline", methods=["POST"])
def run_morning_pipeline():
    # For now, simulate pipeline run synchronously
    simulate_pipeline_run()
    return jsonify({
        "status": "ok",
        "message": "dummy pipeline completed",
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
    # Local testing only; Railway uses gunicorn
    app.run(host="0.0.0.0", port=8080)
